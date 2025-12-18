from flask import Flask, render_template, request, jsonify
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
import urllib
from pathlib import Path
import json
import os


app = Flask(__name__)


# --------------------------
# Database Connection
# --------------------------

# Global engine instance - created once and reused
_db_engine = None

def get_db_engine():
    """Get or create database engine using pymssql connection.
    
    The engine is created once on first call and reused for all subsequent calls.
    This avoids the overhead of creating a new engine for every database query.
    """
    global _db_engine
    
    # Return cached engine if it already exists
    if _db_engine is not None:
        return _db_engine
    
    # Create engine on first call
    config = {}
    config_path = Path(__file__).parent / 'db_config.txt'
    
    if not config_path.exists():
        return None
        
    with open(config_path, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                config[key] = value

    # Use pymssql to build connection string
    conn_str = (
        f"mssql+pymssql://{config['USERNAME']}:{urllib.parse.quote_plus(config['PASSWORD'])}"
        f"@{config['SERVER']}:1433/{config['DATABASE']}"
    )
    try:
        _db_engine = create_engine(conn_str)
        return _db_engine
    except Exception as e:
        print(f"Error creating database engine: {e}")
        return None


def init_db_engine():
    """Initialize the database engine at application startup.
    
    This is optional - the engine will be created lazily on first use if not called.
    Calling this at startup validates the connection early and improves first-request performance.
    """
    engine = get_db_engine()
    if engine:
        # Test the connection by executing a simple query
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database engine initialized successfully.")
        except Exception as e:
            print(f"Database connection test failed: {e}")
    else:
        print("Database engine initialization skipped (no config file or connection failed).")


# --------------------------
# Helper functions (Data Access Layer)
# These are intentionally simple; their names and docstrings
# indicate future responsibilities (DB / ML / ODS integration).
# --------------------------

def get_available_states() -> List[str]:
    """Return list of supported state codes from database.
    
    Falls back to mock data if database is unavailable.
    """
    engine = get_db_engine()
    if engine:
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT DISTINCT State FROM datalake.cms_reference_price_summary ORDER BY State"))
                states = [row[0] for row in result]
                if states:
                    return states
        except Exception:
            pass
    # Return empty list if database is unavailable
    return []


def get_available_areas(state_code: Optional[str] = None) -> List[str]:
    """Return list of available areas (postcodes) from database.
    
    If state_code is provided, filter by state.
    Falls back to empty list if database is unavailable or Area column doesn't exist.
    """
    engine = get_db_engine()
    if engine:
        try:
            if state_code:
                query = text("SELECT DISTINCT Area FROM datalake.cms_reference_price_summary WHERE State = :state AND Area IS NOT NULL ORDER BY Area")
                with engine.connect() as conn:
                    result = conn.execute(query, {"state": state_code})
                    areas = [str(row[0]) for row in result if row[0] is not None]
            else:
                query = text("SELECT DISTINCT Area FROM datalake.cms_reference_price_summary WHERE Area IS NOT NULL ORDER BY Area")
                with engine.connect() as conn:
                    result = conn.execute(query)
                    areas = [str(row[0]) for row in result if row[0] is not None]
            return areas
        except Exception as e:
            print(f"Error fetching areas: {e}")
            # If Area column doesn't exist, return empty list
            pass
    return []


def get_available_metal_levels(state_code: Optional[str] = None, area: Optional[str] = None) -> List[str]:
    """Return list of available metal levels from database.
    
    If state_code and/or area are provided, filter accordingly.
    Falls back to empty list if database is unavailable.
    """
    engine = get_db_engine()
    if engine:
        try:
            conditions = []
            params = {}
            if state_code:
                conditions.append("State = :state")
                params["state"] = state_code
            if area:
                conditions.append("Area = :area")
                params["area"] = area
            
            # Always include MetalLevel IS NOT NULL condition
            conditions.append("MetalLevel IS NOT NULL")
            
            # Build WHERE clause
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = text(f"SELECT DISTINCT MetalLevel FROM datalake.cms_reference_price_summary{where_clause} ORDER BY MetalLevel")
            
            with engine.connect() as conn:
                result = conn.execute(query, params)
                levels = [str(row[0]) for row in result if row[0] is not None]
            return levels
        except Exception as e:
            print(f"Error fetching metal levels: {e}")
            pass
    return []


def get_quote_data(state_code: str, area: str, metal_level: str, age: Optional[str] = None, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Query database for Avg_Price, Avg_Deductible, Avg_MOOP based on state, area, metal level, and age.
    
    Returns dict with avg_price, avg_deductible, avg_moop, or None if not found.
    Handles cases where Area or Age columns might not exist.
    Age can be a string (e.g., '0-14') or numeric string.
    """
    engine = get_db_engine()
    if engine:
        try:
            # Try with Area and Age columns first
            conditions = ["State = :state", "Area = :area", "MetalLevel = :metal_level"]
            params = {"state": state_code, "area": area, "metal_level": metal_level}
            
            if age is not None:
                conditions.append("Age = :age")
                params["age"] = str(age)  # Age is stored as string in database
            
            if year:
                conditions.append("Year = :year")
                params["year"] = year
            
            where_clause = " WHERE " + " AND ".join(conditions)
            query = text(f"""
                SELECT AVG(Avg_Price) as avg_price, 
                       AVG(Avg_Deductible) as avg_deductible, 
                       AVG(Avg_MOOP) as avg_moop
                FROM datalake.cms_reference_price_summary
                {where_clause}
            """)
            
            with engine.connect() as conn:
                result = conn.execute(query, params)
                row = result.fetchone()
                if row and row[0] is not None:
                    return {
                        "avg_price": round(float(row[0]), 2),
                        "avg_deductible": round(float(row[1]), 2),
                        "avg_moop": round(float(row[2]), 2),
                    }
        except Exception as e:
            # If Age column doesn't exist, try without it
            try:
                conditions = ["State = :state", "Area = :area", "MetalLevel = :metal_level"]
                params = {"state": state_code, "area": area, "metal_level": metal_level}
                
                if year:
                    conditions.append("Year = :year")
                    params["year"] = year
                
                where_clause = " WHERE " + " AND ".join(conditions)
                query = text(f"""
                    SELECT AVG(Avg_Price) as avg_price, 
                           AVG(Avg_Deductible) as avg_deductible, 
                           AVG(Avg_MOOP) as avg_moop
                    FROM datalake.cms_reference_price_summary
                    {where_clause}
                """)
                
                with engine.connect() as conn:
                    result = conn.execute(query, params)
                    row = result.fetchone()
                    if row and row[0] is not None:
                        # Apply age adjustment if age is provided but column doesn't exist
                        base_price = float(row[0])
                        if age is not None:
                            # Apply age factor similar to mock_data logic
                            # Parse age string (e.g., '0-14' -> 7, or '25' -> 25)
                            try:
                                if '-' in str(age):
                                    # Age range like '0-14', take middle value
                                    age_parts = str(age).split('-')
                                    age_num = (int(age_parts[0]) + int(age_parts[1])) / 2
                                else:
                                    age_num = float(age)
                                age_factor = 1.0 + ((age_num - 40) / 10.0) * 0.005
                                base_price = base_price * age_factor
                            except (ValueError, TypeError):
                                pass  # Skip age adjustment if parsing fails
                        
                        return {
                            "avg_price": round(base_price, 2),
                            "avg_deductible": round(float(row[1]), 2),
                            "avg_moop": round(float(row[2]), 2),
                        }
            except Exception as e2:
                # If Area column doesn't exist, try without it
                try:
                    conditions = ["State = :state", "MetalLevel = :metal_level"]
                    params = {"state": state_code, "metal_level": metal_level}
                    
                    if age is not None:
                        # Try to add age condition
                        try:
                            conditions.append("Age = :age")
                            params["age"] = age
                        except:
                            pass  # Age column might not exist
                    
                    if year:
                        conditions.append("Year = :year")
                        params["year"] = year
                    
                    where_clause = " WHERE " + " AND ".join(conditions)
                    query = text(f"""
                        SELECT AVG(Avg_Price) as avg_price, 
                               AVG(Avg_Deductible) as avg_deductible, 
                               AVG(Avg_MOOP) as avg_moop
                        FROM datalake.cms_reference_price_summary
                        {where_clause}
                    """)
                    
                    with engine.connect() as conn:
                        result = conn.execute(query, params)
                        row = result.fetchone()
                        if row and row[0] is not None:
                            # Apply age adjustment if age is provided
                            base_price = float(row[0])
                            if age is not None:
                                # Parse age string (e.g., '0-14' -> 7, or '25' -> 25)
                                try:
                                    if '-' in str(age):
                                        # Age range like '0-14', take middle value
                                        age_parts = str(age).split('-')
                                        age_num = (int(age_parts[0]) + int(age_parts[1])) / 2
                                    else:
                                        age_num = float(age)
                                    age_factor = 1.0 + ((age_num - 40) / 10.0) * 0.005
                                    base_price = base_price * age_factor
                                except (ValueError, TypeError):
                                    pass  # Skip age adjustment if parsing fails
                            
                            return {
                                "avg_price": round(base_price, 2),
                                "avg_deductible": round(float(row[1]), 2),
                                "avg_moop": round(float(row[2]), 2),
                            }
                except Exception as e3:
                    print(f"Database query error: {e3}")
                    pass
    return None


def get_available_years() -> List[int]:
    """Return list of available years from database.
    
    Falls back to mock years if database is unavailable.
    """
    engine = get_db_engine()
    if engine:
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT DISTINCT Year FROM datalake.cms_reference_price_summary WHERE Year IS NOT NULL ORDER BY Year"))
                years = [int(row[0]) for row in result if row[0] is not None]
                if years:
                    return years
        except Exception as e:
            print(f"Error fetching years: {e}")
            pass
    # Fallback to mock years
    return [2024, 2025, 2026]


def get_available_years_from_ods() -> List[int]:
    """Return list of available years from ODS premium_summary_aggregated table.
    
    Falls back to mock years if database is unavailable.
    """
    engine = get_db_engine()
    if engine:
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT DISTINCT Year FROM ods.premium_summary_aggregated WHERE Year IS NOT NULL ORDER BY Year"))
                years = [int(row[0]) for row in result if row[0] is not None]
                if years:
                    return years
        except Exception as e:
            print(f"Error fetching years from ODS: {e}")
            pass
    # Fallback to mock years
    return [2024, 2025, 2026]


def get_location_postcode_pairs() -> List[Dict[str, str]]:
    """Return list of all location (State) and postcode (Area) pairs.
    
    First tries to load from local file cache, then from database if cache doesn't exist.
    Returns list of dicts with 'state' and 'area' keys.
    """
    cache_file = Path(__file__).parent / 'cache_location_postcode_pairs.json'
    
    # Try to load from local cache file first
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                if isinstance(cached_data, list) and len(cached_data) > 0:
                    print(f"Loaded {len(cached_data)} location-postcode pairs from local cache")
                    return cached_data
        except Exception as e:
            print(f"Error reading cache file: {e}")
    
    # If cache doesn't exist or is invalid, fetch from database
    engine = get_db_engine()
    pairs = []
    if engine:
        try:
            query = text("SELECT DISTINCT State, Area FROM datalake.cms_reference_price_summary WHERE State IS NOT NULL AND Area IS NOT NULL ORDER BY State, Area")
            with engine.connect() as conn:
                result = conn.execute(query)
                pairs = [{"state": str(row[0]), "area": str(row[1])} for row in result if row[0] is not None and row[1] is not None]
                
                # Save to local cache file
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(pairs, f, indent=2)
                    print(f"Saved {len(pairs)} location-postcode pairs to local cache")
                except Exception as e:
                    print(f"Error saving cache file: {e}")
        except Exception as e:
            print(f"Error fetching location-postcode pairs: {e}")
            pass
    
    return pairs


def get_available_ages() -> List[str]:
    """Return list of available age options (as strings, e.g., '0-14', '15', etc.).
    
    First tries to load from local file cache, then from database if cache doesn't exist.
    Falls back to standard range if database is unavailable.
    """
    cache_file = Path(__file__).parent / 'cache_age_options.json'
    
    # Try to load from local cache file first
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                if isinstance(cached_data, list) and len(cached_data) > 0:
                    print(f"Loaded {len(cached_data)} age options from local cache")
                    # Convert all to strings to handle both string and int formats
                    return [str(age) for age in cached_data]
        except Exception as e:
            print(f"Error reading age cache file: {e}")
    
    # If cache doesn't exist or is invalid, fetch from database
    engine = get_db_engine()
    ages = []
    if engine:
        try:
            query = text("""
                SELECT DISTINCT Age 
                FROM datalake.cms_reference_price_summary 
                WHERE Age IS NOT NULL 
                ORDER BY Age
            """)
            with engine.connect() as conn:
                result = conn.execute(query)
                ages = [str(row[0]) for row in result if row[0] is not None]
                
                if ages:
                    # Save to local cache file
                    try:
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(ages, f, indent=2)
                        print(f"Saved {len(ages)} age options to local cache")
                    except Exception as e:
                        print(f"Error saving age cache file: {e}")
                    return ages
        except Exception as e:
            print(f"Error fetching ages: {e}")
            pass
    
    # Fallback: return standard age range as strings
    fallback_ages = [str(age) for age in range(18, 101)]
    # Save fallback to cache
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(fallback_ages, f, indent=2)
        print(f"Saved fallback age options to local cache")
    except Exception as e:
        print(f"Error saving fallback age cache file: {e}")
    
    return fallback_ages



def get_state_abbreviation_lookup() -> Dict[str, str]:
    """Return a dictionary mapping state abbreviations to full state names.
    
    First tries to load from local file cache, then creates from standard US state list if cache doesn't exist.
    Returns dict with abbreviation as key and full name as value (e.g., {'AL': 'Alabama'}).
    """
    cache_file = Path(__file__).parent / 'cache_state_abbreviation_lookup.json'
    
    # Try to load from local cache file first
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                if isinstance(cached_data, dict) and len(cached_data) > 0:
                    print(f"Loaded state abbreviation lookup from local cache ({len(cached_data)} states)")
                    return cached_data
        except Exception as e:
            print(f"Error reading state lookup cache file: {e}")
    
    # Standard US state abbreviation to full name mapping
    state_lookup = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
        'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
        'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
        'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
        'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
        'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
        'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
        'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
        'DC': 'District of Columbia'
    }
    
    # Save to local cache file
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(state_lookup, f, indent=2)
        print(f"Saved state abbreviation lookup to local cache ({len(state_lookup)} states)")
    except Exception as e:
        print(f"Error saving state lookup cache file: {e}")
    
    return state_lookup


def get_predicted_premium_data_for_year(state_abbrev: str, year: int) -> Optional[Dict[str, Any]]:
    """Query ODS table for predicted premium data for a state and specific year.
    
    Returns dict with:
    - 'predicted': Predicted_Premium for the year
    - 'actual': Actual_Premium for the year
    
    Returns None if data not found or error occurs.
    """
    # Get state full name from abbreviation
    state_lookup = get_state_abbreviation_lookup()
    state_full_name = state_lookup.get(state_abbrev)
    
    if not state_full_name:
        print(f"State abbreviation '{state_abbrev}' not found in lookup table")
        return None
    
    engine = get_db_engine()
    if not engine:
        return None
    
    try:
        query = text("""
            SELECT Year, Predicted_Premium, Actual_Premium
            FROM ods.premium_summary_aggregated
            WHERE Year = :year
              AND State = :state
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"state": state_full_name, "year": year})
            row = result.fetchone()
            
            if row:
                predicted = float(row[1]) if row[1] is not None else None
                actual = float(row[2]) if row[2] is not None else None
                
                return {
                    'predicted': predicted,
                    'actual': actual
                }
            else:
                return None
                
    except Exception as e:
        print(f"Error fetching predicted premium data for {state_full_name} in {year}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_predicted_premium_data(state_abbrev: str) -> Optional[Dict[str, Any]]:
    """Query ODS table for predicted premium data for a state.
    
    Returns dict with:
    - 'predicted_2024': Predicted_Premium for 2024
    - 'actual_2024': Actual_Premium for 2024
    - 'predicted_2025': Predicted_Premium for 2025
    - 'actual_2025': Actual_Premium for 2025 (if available)
    
    Returns None if data not found or error occurs.
    """
    # Get state full name from abbreviation
    state_lookup = get_state_abbreviation_lookup()
    state_full_name = state_lookup.get(state_abbrev)
    
    if not state_full_name:
        print(f"State abbreviation '{state_abbrev}' not found in lookup table")
        return None
    
    engine = get_db_engine()
    if not engine:
        return None
    
    try:
        query = text("""
            SELECT Year, Predicted_Premium, Actual_Premium
            FROM ods.premium_summary_aggregated
            WHERE Year IN (2024, 2025)
              AND State = :state
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"state": state_full_name})
            data = {}
            for row in result:
                year = int(row[0])
                predicted = float(row[1]) if row[1] is not None else None
                actual = float(row[2]) if row[2] is not None else None
                
                if year == 2024:
                    data['predicted_2024'] = predicted
                    data['actual_2024'] = actual
                elif year == 2025:
                    data['predicted_2025'] = predicted
                    data['actual_2025'] = actual
            
            # Return data if we have at least the required fields
            if 'predicted_2024' in data and data['predicted_2024'] is not None and \
               'actual_2024' in data and data['actual_2024'] is not None and \
               'predicted_2025' in data and data['predicted_2025'] is not None:
                return data
            else:
                print(f"Incomplete prediction data for state {state_full_name}: {data}")
                return None
                
    except Exception as e:
        print(f"Error fetching predicted premium data for {state_full_name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_estimated_premium_next_year(current_premium: float, state_abbrev: str) -> Optional[float]:
    """Calculate estimated premium for next year based on prediction data.
    
    Formula: current_premium * (actual_2025 / predicted_2025)
    
    Uses actual premium in 2025 divided by predicted premium in 2025, multiplied by current estimated premium.
    Returns None if prediction data is not available.
    """
    prediction_data = get_predicted_premium_data(state_abbrev)
    
    if not prediction_data:
        return None
    
    predicted_2025 = prediction_data.get('predicted_2025')
    actual_2025 = prediction_data.get('actual_2025')
    
    if predicted_2025 is None or actual_2025 is None or predicted_2025 == 0:
        return None
    
    try:
        estimated = current_premium * (actual_2025 / predicted_2025)
        return round(estimated, 2)
    except (TypeError, ZeroDivisionError) as e:
        print(f"Error calculating estimated premium: {e}")
        return None


# --------------------------
# Web Routes
# --------------------------


@app.route("/", methods=["GET"])
def index():
    # Landing page that clearly offers the two main use-cases to the user.
    return render_template("index.html")


@app.route("/api/states", methods=["GET"])
def api_states():
    """API endpoint to get available states."""
    states = get_available_states()
    return jsonify({"states": states})


@app.route("/api/years", methods=["GET"])
def api_years():
    """API endpoint to get available years."""
    years = get_available_years()
    return jsonify({"years": years})


@app.route("/api/location-postcode-pairs", methods=["GET"])
def api_location_postcode_pairs():
    """API endpoint to get all location (State) and postcode (Area) pairs from cache."""
    # This loads from cache file if available, otherwise fetches from DB and caches
    pairs = get_location_postcode_pairs()
    return jsonify({"pairs": pairs})


@app.route("/api/ages", methods=["GET"])
def api_ages():
    """API endpoint to get available age options from cache."""
    # This loads from cache file if available, otherwise fetches from DB and caches
    ages = get_available_ages()
    return jsonify({"ages": ages})


@app.route("/api/areas", methods=["GET"])
def api_areas():
    """API endpoint to get available areas for a state."""
    state = request.args.get("state")
    areas = get_available_areas(state) if state else get_available_areas()
    return jsonify({"areas": areas})


@app.route("/api/metal-levels", methods=["GET"])
def api_metal_levels():
    """API endpoint to get available metal levels for a state and area."""
    state = request.args.get("state")
    area = request.args.get("area")
    metal_levels = get_available_metal_levels(state, area)
    return jsonify({"metal_levels": metal_levels})


@app.route("/api/plan-options", methods=["GET"])
def api_plan_options():
    """API endpoint to get metal level options with pricing for a state, area, and age.
    
    Returns metal levels with their avg_price, avg_deductible, and avg_moop for the given age.
    Age is mandatory and can be a string (e.g., '0-14') or integer.
    """
    state = request.args.get("state")
    area = request.args.get("area")
    year = request.args.get("year", "2025")  # Default to 2025
    age = request.args.get("age")
    
    if not state or not area:
        return jsonify({"error": "State and area are required"}), 400
    
    if not age:
        return jsonify({"error": "Age is required"}), 400
    
    # Age can be a string (e.g., '0-14') or integer, so we keep it as string
    age_str = str(age).strip()
    
    engine = get_db_engine()
    options = []
    
    if engine:
        try:
            # Query metal levels for the given state, area, year, and age (age is a string)
            query = text("""
                SELECT MetalLevel,
                       AVG(Avg_Price) as avg_price, 
                       AVG(Avg_Deductible) as avg_deductible, 
                       AVG(Avg_MOOP) as avg_moop
                FROM datalake.cms_reference_price_summary
                WHERE State = :state AND Area = :area AND Year = :year AND Age = :age
                  AND MetalLevel IS NOT NULL
                GROUP BY MetalLevel
                ORDER BY MetalLevel
            """)
            
            with engine.connect() as conn:
                result = conn.execute(query, {"state": state, "area": area, "year": int(year), "age": age_str})
                row_count = 0
                for row in result:
                    row_count += 1
                    if row[0] is None:  # Skip if MetalLevel is None
                        continue
                    avg_price = round(float(row[1]), 2) if row[1] is not None else 0.0
                    # Calculate estimated premium next year
                    estimated_next_year = calculate_estimated_premium_next_year(avg_price, state)
                    
                    option_data = {
                        "metal_level": str(row[0]).strip(),
                        "avg_price": avg_price,
                        "avg_deductible": round(float(row[2]), 2) if row[2] is not None else 0.0,
                        "avg_moop": round(float(row[3]), 2) if row[3] is not None else 0.0,
                    }
                    
                    if estimated_next_year is not None:
                        option_data["estimated_premium_next_year"] = estimated_next_year
                    
                    options.append(option_data)
                print(f"Found {row_count} rows, {len(options)} valid options for state={state}, area={area}, year={year}, age={age_str}")
        except Exception as e:
            print(f"Error fetching plan options with Age column: {e}")
            import traceback
            traceback.print_exc()
            # Try without Age column (apply age adjustment if age is numeric)
            try:
                query = text("""
                    SELECT MetalLevel, 
                           AVG(Avg_Price) as avg_price, 
                           AVG(Avg_Deductible) as avg_deductible, 
                           AVG(Avg_MOOP) as avg_moop
                    FROM datalake.cms_reference_price_summary
                    WHERE State = :state AND Area = :area AND Year = :year
                      AND MetalLevel IS NOT NULL
                    GROUP BY MetalLevel
                    ORDER BY MetalLevel
                """)
                
                with engine.connect() as conn:
                    result = conn.execute(query, {"state": state, "area": area, "year": int(year)})
                    for row in result:
                        base_price = float(row[1])
                        # Try to apply age adjustment if age is numeric
                        try:
                            # If age is a range like '0-14', use the middle value
                            if '-' in age_str:
                                age_parts = age_str.split('-')
                                age_int = (int(age_parts[0]) + int(age_parts[1])) // 2
                            else:
                                age_int = int(age_str)
                            age_factor = 1.0 + ((age_int - 40) / 10.0) * 0.005
                            adjusted_price = base_price * age_factor
                        except (ValueError, TypeError):
                            # If age is not numeric, use base price
                            adjusted_price = base_price
                        
                        avg_price = round(adjusted_price, 2)
                        # Calculate estimated premium next year
                        estimated_next_year = calculate_estimated_premium_next_year(avg_price, state)
                        
                        option_data = {
                            "metal_level": str(row[0]),
                            "avg_price": avg_price,
                            "avg_deductible": round(float(row[2]), 2),
                            "avg_moop": round(float(row[3]), 2),
                        }
                        
                        if estimated_next_year is not None:
                            option_data["estimated_premium_next_year"] = estimated_next_year
                        
                        options.append(option_data)
            except Exception as e2:
                print(f"Error fetching plan options (fallback): {e2}")
    
    return jsonify({"options": options})


@app.route("/quote", methods=["GET", "POST"])
def quote():
    # For GET requests, use empty list initially (will be populated by AJAX)
    # For POST requests, use cached states for validation
    if request.method == "POST":
        # Cache states list to avoid repeated database calls
        states = get_available_states()
    else:
        states = []  # Will be populated by AJAX on page load
    
    selected_state = None
    selected_area = None
    selected_metal_level = None
    selected_age = None
    areas: List[str] = []
    metal_levels: List[str] = []
    result = None
    error_message = None

    if request.method == "POST":
        form = request.form
        selected_state = form.get("state")
        selected_area = form.get("area", "").strip()
        selected_metal_level = form.get("metal_level")
        age_raw = form.get("age")
        
        # Parse age
        try:
            selected_age = str(age_raw) if age_raw else None
        except (TypeError, ValueError):
            selected_age = None

        # Quick validation (use cached states list, don't call get_available_states() again)
        if not selected_state or selected_state not in states:
            error_message = "Please select a valid state."
        elif not selected_area:
            error_message = "Please enter the area code."
        elif not selected_metal_level:
            error_message = "Please select a metal level."
        elif not selected_age:
            error_message = "Please enter your age."
        else:
            # Year is fixed to 2025
            selected_year = 2025
            
            # Check if pricing data was submitted from preview (to avoid re-querying database)
            avg_price = form.get("avg_price")
            avg_deductible = form.get("avg_deductible")
            avg_moop = form.get("avg_moop")
            
            if avg_price and avg_deductible and avg_moop:
                # Use data from preview (already cached, no database query needed)
                try:
                    result = {
                        "avg_price": round(float(avg_price), 2),
                        "avg_deductible": round(float(avg_deductible), 2),
                        "avg_moop": round(float(avg_moop), 2),
                    }
                    # Skip predicted data calculation for speed - it's optional and can be slow
                    # If needed, it can be calculated asynchronously or on-demand
                except (ValueError, TypeError) as e:
                    print(f"Error parsing preview data: {e}")
                    # Fallback to database query if preview data is invalid
                    quote_data = get_quote_data(selected_state, selected_area, selected_metal_level, age=selected_age, year=selected_year)
                    if quote_data:
                        result = quote_data
                        # Skip predicted data for speed
                    else:
                        error_message = "No data found for the selected location, area code, and metal level combination."
            else:
                # No preview data available, query database
                quote_data = get_quote_data(selected_state, selected_area, selected_metal_level, age=selected_age, year=selected_year)
                if quote_data:
                    result = quote_data
                    # Skip predicted data for speed - can be added later if needed
                else:
                    error_message = "No data found for the selected location, area code, and metal level combination."

    # GET request or after POST - populate dropdowns
    if request.method == "GET":
        # Get state from query params if available
        selected_state = request.args.get("state")
        selected_area = request.args.get("area")
        selected_metal_level = request.args.get("metal_level")
        age_raw = request.args.get("age")
        year_raw = request.args.get("year")
        try:
            selected_age = int(age_raw) if age_raw else None
        except (TypeError, ValueError):
            selected_age = None
        try:
            selected_year = int(year_raw) if year_raw else None
        except (TypeError, ValueError):
            selected_year = None
    
    # For GET requests, don't query database - let JavaScript load data asynchronously
    # Only provide initial values if coming from query params (for pre-filled forms from apply page)
    areas: List[str] = []
    metal_levels: List[str] = []
    
    # Only query areas/metal levels if we have POST data or specific query params (for pre-filled forms)
    if request.method == "POST" or (selected_state and selected_area):
        if selected_state:
            areas = get_available_areas(selected_state)
        else:
            areas = get_available_areas()
        
        if selected_state and selected_area:
            metal_levels = get_available_metal_levels(selected_state, selected_area)
        elif selected_state:
            metal_levels = get_available_metal_levels(selected_state)
        else:
            metal_levels = get_available_metal_levels()

    selected_year = selected_year if 'selected_year' in locals() else None
    
    return render_template(
        "quote.html",
        states=states,
        selected_state=selected_state,
        areas=areas,
        selected_area=selected_area,
        metal_levels=metal_levels,
        selected_metal_level=selected_metal_level,
        selected_age=selected_age,
        selected_year=selected_year,
        result=result,
        error_message=error_message,
    )


@app.route("/analytics", methods=["GET", "POST"])
def analytics():
    states = get_available_states()
    years = get_available_years_from_ods()
    selected_state = None
    selected_year = None
    predicted_base_rate = None
    prediction_data = None
    error_message = None

    if request.method == "POST":
        selected_state = request.form.get("state")
        year_raw = request.form.get("year")

        try:
            selected_year = int(year_raw) if year_raw else None
        except ValueError:
            selected_year = None

        if not selected_state or selected_state not in states:
            error_message = "Please select a valid state."
        elif not selected_year or selected_year not in years:
            error_message = "Please select a valid year."
        else:
            # Get prediction data from ODS for the selected year
            prediction_data = get_predicted_premium_data_for_year(selected_state, selected_year)
            
            if prediction_data:
                predicted_base_rate = prediction_data.get('predicted')
                if predicted_base_rate is not None:
                    predicted_base_rate = round(float(predicted_base_rate), 2)
                else:
                    error_message = f"No predicted premium available for {selected_state} in {selected_year}."
            else:
                error_message = f"No prediction data available for {selected_state} in {selected_year}."

    return render_template(
        "analytics.html",
        states=states,
        years=years,
        selected_state=selected_state,
        selected_year=selected_year,
        predicted_base_rate=predicted_base_rate,
        prediction_data=prediction_data,
        error_message=error_message,
    )


@app.route("/apply", methods=["GET", "POST"])
def apply():
    # Application entry point — pre-filled from quote selections
    if request.method == "GET":
        state = request.args.get("state")
        area = request.args.get("area")
        metal_level = request.args.get("metal_level")
        age = request.args.get("age")
        year = request.args.get("year")
        avg_price = request.args.get("avg_price")
        avg_deductible = request.args.get("avg_deductible")
        avg_moop = request.args.get("avg_moop")
        
        return render_template(
            "apply.html",
            state=state,
            area=area,
            metal_level=metal_level,
            age=age,
            year=year,
            avg_price=avg_price,
            avg_deductible=avg_deductible,
            avg_moop=avg_moop,
        )

    # POST: simple submission handling — no persistence, just confirmation
    form = request.form
    state = form.get("state")
    area = form.get("area")
    metal_level = form.get("metal_level")
    age = form.get("age")
    year = form.get("year")
    avg_price = form.get("avg_price")
    avg_deductible = form.get("avg_deductible")
    avg_moop = form.get("avg_moop")
    customer_name = form.get("customer_name")
    email = form.get("email")
    phone = form.get("phone")
    address = form.get("address")

    # minimal validation
    missing = []
    if not customer_name:
        missing.append("customer name")
    if not email:
        missing.append("email")

    if missing:
        return render_template(
            "apply.html", 
            state=state, 
            area=area, 
            metal_level=metal_level,
            age=age,
            year=year,
            avg_price=avg_price,
            avg_deductible=avg_deductible,
            avg_moop=avg_moop,
            customer_name=customer_name, 
            email=email, 
            phone=phone, 
            address=address, 
            message=f"Please fill required fields: {', '.join(missing)}"
        )

    # pretend to create an application — return confirmation
    message = f"Application submitted for {customer_name}. We sent a confirmation to {email}."
    return render_template(
        "apply.html", 
        state=state, 
        area=area, 
        metal_level=metal_level,
        age=age,
        year=year,
        avg_price=avg_price,
        avg_deductible=avg_deductible,
        avg_moop=avg_moop,
        customer_name=customer_name, 
        email=email, 
        phone=phone, 
        address=address, 
        message=message
    )


if __name__ == "__main__":
    # Initialize database engine at startup for better performance
    init_db_engine()
    # For local development only. In production, use a WSGI server.
    app.run(debug=True, host="127.0.0.1", port=5000)
