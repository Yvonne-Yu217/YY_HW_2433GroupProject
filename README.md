# Insurance Quote & Analytics Portal

This project is a comprehensive web application designed to provide real-time insurance quotes and in-depth market analytics. It serves two primary user groups: Customers seeking insurance plans and Internal Staff analyzing market trends.

## Project Overview

The application integrates a robust data pipeline (Raw Data -> Data Lake -> Data Warehouse) with a user-friendly web interface. It leverages machine learning models to provide accurate premium estimations and data-driven insights.

### Key Features

*   **Real-Time Quote Generation:** Users can input their demographic and location data to receive instant, personalized insurance quotes.
*   **Market Analytics:** Interactive dashboards for visualizing historical price trends and predicting future premiums.
*   **End-to-End Integration:** Seamless connection between the frontend web app and the backend SQL Server database and ML models.

## Application Demo

### 1. Customer Portal (Quote & Apply)
The customer-facing interface allows users to easily navigate, get quotes, and apply for insurance plans.

![Customer Portal Demo](../report/Customer.gif)

*Figure 1: Customer workflow - from landing page to generating a quote.*

### 2. Staff Dashboard (Analytics)
The internal dashboard provides staff with powerful tools to analyze market data, view price trends across different states, and make informed decisions.

![Staff Dashboard Demo](../report/Stuff.gif)

*Figure 2: Staff workflow - accessing analytics and visualizing data trends.*

## How to Run

1.  **Prerequisites:** Ensure Python 3.8+ is installed.
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the Application:**
    ```bash
    python app.py
    ```
4.  **Access the App:** Open your browser and navigate to `http://127.0.0.1:5001`.

## Tech Stack

*   **Frontend:** HTML, CSS, JavaScript, Bootstrap
*   **Backend:** Python, Flask
*   **Database:** Azure SQL Database
*   **Data Analysis:** Pandas, Scikit-learn
