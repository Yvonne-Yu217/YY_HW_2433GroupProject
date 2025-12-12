import pandas as pd
import numpy as np
from pathlib import Path
import joblib
import os
import warnings
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

warnings.filterwarnings('ignore')

class HealthcarePremiumPipeline:
    def __init__(self):
        # Base Model
        self.base_model = XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            early_stopping_rounds=20,
            eval_metric='rmse'
        )
        
        # Residual Model
        self.residual_model = XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            early_stopping_rounds=20,
            eval_metric='rmse'
        )
        
        self.imputer = SimpleImputer(strategy='median')
        self.scaler = StandardScaler()
        self.le_metal = LabelEncoder()
        
        # Mappings
        self.state_fips_to_name = {
            1: 'Alabama', 2: 'Alaska', 4: 'Arizona', 5: 'Arkansas', 6: 'California',
            8: 'Colorado', 9: 'Connecticut', 10: 'Delaware', 12: 'Florida', 13: 'Georgia',
            15: 'Hawaii', 16: 'Idaho', 17: 'Illinois', 18: 'Indiana', 19: 'Iowa',
            20: 'Kansas', 21: 'Kentucky', 22: 'Louisiana', 23: 'Maine', 24: 'Maryland',
            25: 'Massachusetts', 26: 'Michigan', 27: 'Minnesota', 28: 'Mississippi',
            29: 'Missouri', 30: 'Montana', 31: 'Nebraska', 32: 'Nevada', 33: 'New Hampshire',
            34: 'New Jersey', 35: 'New Mexico', 36: 'New York', 37: 'North Carolina',
            38: 'North Dakota', 39: 'Ohio', 40: 'Oklahoma', 41: 'Oregon', 42: 'Pennsylvania',
            44: 'Rhode Island', 45: 'South Carolina', 46: 'South Dakota', 47: 'Tennessee',
            48: 'Texas', 49: 'Utah', 50: 'Vermont', 51: 'Virginia', 53: 'Washington',
            54: 'West Virginia', 55: 'Wisconsin', 56: 'Wyoming'
        }
        
        self.health_feature_mapping = {
            'mean_BMI_w': 'bmi_avg',
            'diabetes_prev_w': 'diabetes_prev',
            'asthma_now_prev_w': 'asthma_curr_prev',
            'copd_prev_w': 'copd_prev',
            'chd_prev_w': 'chd_prev',
            'stroke_prev_w': 'stroke_prev',
            'kidney_disease_prev_w': 'kidney_prev',
            'arthritis_prev_w': 'arthritis_prev',
            'any_cancer_prev_w': 'cancer_prev',
            'current_smoker_prev_w': 'current_smoker_prev'
        }
        
        self.feature_cols = [] # Will be populated during training

    def _extract_metal_tier(self, tier_raw):
        """Extract metal tier name from column name"""
        if 'Bronze' in tier_raw:
            return 'Bronze'
        elif 'Silver' in tier_raw or 'Benchmark' in tier_raw:
            return 'Silver'
        elif 'Gold' in tier_raw:
            return 'Gold'
        else:
            return 'Unknown'

    def load_data(self, kff_path, cdc_path):
        """Load raw datasets"""
        print(f"Loading KFF data from {kff_path}...")
        kff_df = pd.read_csv(kff_path)
        
        print(f"Loading CDC data from {cdc_path}...")
        cdc_df = pd.read_csv(cdc_path)
        
        return kff_df, cdc_df

    def preprocess_kff(self, kff_df):
        """Convert KFF data from Wide to Long format"""
        kff_long = pd.melt(
            kff_df,
            id_vars=['Location', 'Year'],
            value_vars=['Average Lowest-Cost Bronze Premium', 
                        'Average Lowest-Cost Silver Premium', 
                        'Average Benchmark Premium', 
                        'Average Lowest-Cost Gold Premium'],
            var_name='Metal_Tier_Raw',
            value_name='Premium_Y'
        )
        
        kff_long['Metal_Tier'] = kff_long['Metal_Tier_Raw'].apply(self._extract_metal_tier)
        kff_long = kff_long.drop('Metal_Tier_Raw', axis=1)
        
        # Clean Premium_Y
        if kff_long['Premium_Y'].dtype == 'object':
            kff_long['Premium_Y'] = kff_long['Premium_Y'].str.replace('$', '').str.replace(',', '').astype(float)
            
        return kff_long

    def preprocess_cdc(self, cdc_df):
        """Prepare CDC features"""
        # Map _STATE to Location if needed
        if 'Location' not in cdc_df.columns and '_STATE' in cdc_df.columns:
            cdc_df['Location'] = cdc_df['_STATE'].map(self.state_fips_to_name)
            
        # Select and rename columns
        available_cdc_cols = [col for col in self.health_feature_mapping.keys() if col in cdc_df.columns]
        select_cols = ['Location', 'IYEAR'] + available_cdc_cols
        cdc_features = cdc_df[select_cols].copy()
        
        rename_dict = {'IYEAR': 'CDC_Year'}
        rename_dict.update(self.health_feature_mapping)
        cdc_features = cdc_features.rename(columns=rename_dict)
        
        return cdc_features

    def add_trend_features(self, df, kff_long):
        """Add lagged premium and trend features"""
        print("Adding trend features (lags and year-over-year changes)...")
        
        # Create pivot for lookups
        premium_pivot = kff_long.pivot_table(
            index=['Location', 'Metal_Tier'],
            columns='Year',
            values='Premium_Y',
            aggfunc='first'
        )
        
        df = df.copy()
        df['premium_lag1'] = np.nan
        df['premium_lag2'] = np.nan
        df['trend_1y'] = np.nan
        df['trend_2y_avg'] = np.nan
        
        # Vectorized approach would be faster, but sticking to iterative for safety/clarity as per notebook logic
        # Optimizing slightly by using map/apply if possible, but loop is robust for now
        
        for idx, row in df.iterrows():
            location = row['Location']
            metal_tier = row['Metal_Tier']
            year = row['KFF_Year']
            
            try:
                if (location, metal_tier) in premium_pivot.index:
                    premium_data = premium_pivot.loc[(location, metal_tier)]
                    
                    if year - 1 in premium_data.index:
                        df.loc[idx, 'premium_lag1'] = premium_data[year - 1]
                    if year - 2 in premium_data.index:
                        df.loc[idx, 'premium_lag2'] = premium_data[year - 2]
                    
                    if not pd.isna(df.loc[idx, 'premium_lag1']) and not pd.isna(df.loc[idx, 'premium_lag2']):
                        df.loc[idx, 'trend_1y'] = df.loc[idx, 'premium_lag1'] - df.loc[idx, 'premium_lag2']
                        df.loc[idx, 'trend_2y_avg'] = df.loc[idx, 'trend_1y'] / 2
            except Exception:
                pass
                
        return df

    def merge_data(self, kff_long, cdc_features):
        """Merge KFF and CDC data and add trends"""
        cdc_same_year = cdc_features.copy()
        cdc_same_year['KFF_Year'] = cdc_same_year['CDC_Year']
        
        merged_df = pd.merge(
            cdc_same_year,
            kff_long,
            left_on=['Location', 'KFF_Year'],
            right_on=['Location', 'Year'],
            how='inner'
        )
        merged_df = merged_df.drop('Year', axis=1)
        
        # Add trends
        merged_df = self.add_trend_features(merged_df, kff_long)
        
        return merged_df

    def prepare_features(self, df, training=True):
        """Prepare X and y for modeling"""
        # Identify feature columns
        health_cols = [col for col in self.health_feature_mapping.values() if col in df.columns]
        trend_cols = ['premium_lag1', 'premium_lag2', 'trend_1y', 'trend_2y_avg']
        
        feature_cols = health_cols + ['Metal_Tier'] + trend_cols
        
        if training:
            self.feature_cols = feature_cols
            # Fit LabelEncoder
            self.le_metal.fit(df['Metal_Tier'])
        
        X = df[self.feature_cols].copy()
        
        # Encode Metal_Tier
        X['Metal_Tier_Encoded'] = self.le_metal.transform(X['Metal_Tier'])
        X = X.drop('Metal_Tier', axis=1)
        
        if training:
            self.imputer.fit(X)
            X_imputed = self.imputer.transform(X)
            self.scaler.fit(X_imputed)
            X_scaled = self.scaler.transform(X_imputed)
        else:
            X_imputed = self.imputer.transform(X)
            X_scaled = self.scaler.transform(X_imputed)
            
        y = df['Premium_Y'] if 'Premium_Y' in df.columns else None
        
        return X_scaled, y

    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train Base Model + Residual Model"""
        print("Training Base XGBoost Model (with Trends)...")
        eval_set = [(X_val, y_val)] if X_val is not None else None
        
        self.base_model.fit(
            X_train, 
            y_train,
            eval_set=eval_set,
            verbose=False
        )
        
        # Generate predictions for residual training
        y_train_pred = self.base_model.predict(X_train)
        train_residuals = y_train - y_train_pred
        
        val_residuals = None
        if X_val is not None and y_val is not None:
            y_val_pred = self.base_model.predict(X_val)
            val_residuals = y_val - y_val_pred
            
        print("Training Residual XGBoost Model...")
        eval_set_res = [(X_val, val_residuals)] if val_residuals is not None else None
        
        self.residual_model.fit(
            X_train,
            train_residuals,
            eval_set=eval_set_res,
            verbose=False
        )
        print("Training complete.")

    def predict(self, X):
        """Make combined predictions"""
        base_pred = self.base_model.predict(X)
        residual_pred = self.residual_model.predict(X)
        return base_pred + residual_pred

    def evaluate(self, X, y, dataset_name="Dataset"):
        """Evaluate model performance"""
        y_pred = self.predict(X)
        
        r2 = r2_score(y, y_pred)
        mae = mean_absolute_error(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        mape = np.mean(np.abs((y - y_pred) / y)) * 100
        
        print(f"{dataset_name}: R²={r2:.4f}, MAE=${mae:.2f}, RMSE=${rmse:.2f}, MAPE={mape:.2f}%")
        return {'R2': r2, 'MAE': mae, 'RMSE': rmse, 'MAPE': mape}

    def save(self, filepath):
        """Save the entire pipeline"""
        joblib.dump(self, filepath)
        print(f"Pipeline saved to {filepath}")

    @staticmethod
    def load(filepath):
        """Load a saved pipeline"""
        return joblib.load(filepath)

def main():
    # Configuration
    BASE_DIR = Path(__file__).parent
    KFF_PATH = BASE_DIR / '2433_p3_data/KFF_data/exports/kff_combined_2018_2026.csv'
    CDC_PATH = BASE_DIR / '2433_p3_data/healthcare.gov/exports/aggregated/aggregated_all_years.csv'
    MODEL_PATH = BASE_DIR / 'healthcare_premium_combined_model.joblib'
    
    # Initialize Pipeline
    pipeline = HealthcarePremiumPipeline()
    
    # 1. Load Data
    if not KFF_PATH.exists() or not CDC_PATH.exists():
        print(f"Data files not found.\nKFF: {KFF_PATH}\nCDC: {CDC_PATH}")
        return

    kff_df, cdc_df = pipeline.load_data(KFF_PATH, CDC_PATH)
    
    # 2. Preprocess
    kff_long = pipeline.preprocess_kff(kff_df)
    cdc_features = pipeline.preprocess_cdc(cdc_df)
    merged_df = pipeline.merge_data(kff_long, cdc_features)
    
    print(f"Merged dataset shape: {merged_df.shape}")
    
    # 3. Split Data (With Trends: Train 2020-2022, Val 2023, Test 2024)
    # Note: We need 2018-2019 data to calculate lags for 2020, so we filter AFTER merging/lags
    train_df = merged_df[merged_df['KFF_Year'].isin([2020, 2021, 2022])].copy()
    val_df = merged_df[merged_df['KFF_Year'].isin([2023])].copy()
    test_df = merged_df[merged_df['KFF_Year'] == 2024].copy()
    
    print(f"Train samples: {len(train_df)}, Val samples: {len(val_df)}, Test samples: {len(test_df)}")
    
    # 4. Prepare Features
    X_train, y_train = pipeline.prepare_features(train_df, training=True)
    X_val, y_val = pipeline.prepare_features(val_df, training=False)
    X_test, y_test = pipeline.prepare_features(test_df, training=False)
    
    # 5. Train
    pipeline.train(X_train, y_train, X_val, y_val)
    
    # 6. Evaluate
    print("\nModel Evaluation (Combined Model: Base + Residuals):")
    pipeline.evaluate(X_train, y_train, "Train")
    pipeline.evaluate(X_val, y_val, "Validation")
    pipeline.evaluate(X_test, y_test, "Test")
    
    # 7. Save Model
    pipeline.save(MODEL_PATH)

if __name__ == "__main__":
    main()
