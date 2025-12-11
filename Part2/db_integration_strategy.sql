-- =====================================================================
-- Database Integration Strategy (T-SQL for Azure SQL)
-- 数据库整合策略：连接 EDA 业务数据与美国慢性病分析数据
-- File: db_integration_strategy.sql
-- Updated: 2025-11-09 for Azure SQL Database (Fixed)
--
-- CORE CONCEPT / 核心思路:
-- Connect EDA business data with US Chronic Disease analytics data 
-- using geographic location (State) as the bridge.
-- 通过地理位置（州）作为桥梁，将客户/账户数据与慢性病指标数据进行连接。
--
-- STRATEGY STEPS / 策略步骤:
-- 1. Create Bridge Table (integration.CustomerLocationBridge) 
--    to store customer/account location info
-- 2. Create Unified Location View (integration.vw_UnifiedLocationDim)
--    to simplify geographic dimension joins
-- 3. Create Final Analysis View (integration.vw_CustomerHealthRiskAnalysis)
--    as a wide table for BI tools
--
-- ADVANTAGES / 优点:
-- - Non-invasive: doesn't modify existing business or analytics tables
-- - Performance: pre-computed bridge table with indexes
-- - Easy to use: final view hides complex join logic
-- =====================================================================

-- =====================================================================
-- PREREQUISITES / 前提条件:
-- 1. Schema: eda (contains Customer, CustomerAddress, Account, State tables)
-- 2. Schema: dw (contains DimLocations, DimTopics, DimQuestions, FactHealthObservations)
-- 3. Both schemas should be in the same database (2433-db)
-- =====================================================================

-- =====================================================================
-- STEP 1: Create Integration Schema and Bridge Table
-- 步骤 1: 创建集成架构和桥梁表
--
-- PURPOSE / 目的:
-- Extract key customer/account location information from complex business tables
-- to avoid expensive joins every query.
-- 从复杂的业务表中提取关键的客户/账户位置信息，避免每次查询都做昂贵的连接。
--
-- DESIGN / 设计:
-- - CustomerKey: Customer unique ID (LastName|FirstName|MiddleInitial|Suffix|DOB)
-- - AccountKey: Account unique ID (AccountName|LocationAddress1|LocationCity|LocationState|LocationZip|CompanyCode)
-- - StateCode: State code (2-letter abbreviation, e.g., 'CA', 'NY')
-- - RecordType: 'Customer' or 'Account'
-- =====================================================================

-- Create integration schema
IF SCHEMA_ID(N'integration') IS NULL
    EXEC('CREATE SCHEMA integration;');
GO

-- Drop and recreate bridge table
IF OBJECT_ID('integration.CustomerLocationBridge', 'U') IS NOT NULL
    DROP TABLE integration.CustomerLocationBridge;
GO

CREATE TABLE integration.CustomerLocationBridge (
    BridgeID        INT IDENTITY(1,1) PRIMARY KEY,
    CustomerKey     NVARCHAR(400) NULL,  -- Format: LastName|FirstName|MiddleInitial|Suffix|DOB
    AccountKey      NVARCHAR(400) NULL,  -- Format: AccountName|LocationAddress1|LocationCity|LocationState|LocationZip|CompanyCode
    StateCode       NVARCHAR(2) NOT NULL,  -- 2-letter state code (matches State.StateCode)
    RecordType      NVARCHAR(20) NOT NULL,  -- 'Customer' or 'Account'
    LastUpdated     DATETIME2(3) NOT NULL CONSTRAINT DF_Bridge_LastUpdated DEFAULT SYSUTCDATETIME()
    -- Note: UNIQUE constraint removed due to key length limitation (max 1700 bytes)
    -- Uniqueness will be enforced by NOT EXISTS in INSERT statements
);
GO

-- Create indexes for performance
-- Note: SET QUOTED_IDENTIFIER must be ON for filtered indexes
SET QUOTED_IDENTIFIER ON;
GO

CREATE NONCLUSTERED INDEX IX_Bridge_StateCode 
    ON integration.CustomerLocationBridge(StateCode);
GO

CREATE NONCLUSTERED INDEX IX_Bridge_CustomerKey 
    ON integration.CustomerLocationBridge(CustomerKey) 
    WHERE CustomerKey IS NOT NULL;
GO

CREATE NONCLUSTERED INDEX IX_Bridge_AccountKey 
    ON integration.CustomerLocationBridge(AccountKey) 
    WHERE AccountKey IS NOT NULL;
GO

CREATE NONCLUSTERED INDEX IX_Bridge_RecordType 
    ON integration.CustomerLocationBridge(RecordType);
GO

-- Create composite index for uniqueness check
CREATE NONCLUSTERED INDEX IX_Bridge_Uniqueness 
    ON integration.CustomerLocationBridge(StateCode, RecordType, CustomerKey, AccountKey);
GO


-- =====================================================================
-- STEP 1.1: Populate Bridge Table (ETL Process)
-- 步骤 1.1: 填充桥梁表 (ETL 过程)
--
-- PURPOSE / 目的:
-- Load customer and account location data from business tables into bridge table.
-- This should be a scheduled ETL job (e.g., daily or weekly).
-- 将业务表的客户和账户位置数据加载到桥梁表中。这应该是定期的 ETL 作业。
-- =====================================================================

-- Load Customer location data from CustomerAddress
-- Note: Uses eda schema prefix
INSERT INTO integration.CustomerLocationBridge (CustomerKey, AccountKey, StateCode, RecordType)
SELECT DISTINCT
    CONCAT(c.CustLastName, '|', c.CustFirstName, '|', c.CustMiddleInitial, '|', c.CustSuffix, '|', CONVERT(NVARCHAR(10), c.CustDOB, 120)) AS CustomerKey,
    NULL AS AccountKey,
    ca.CustState AS StateCode,  -- This should be 2-letter state code
    N'Customer' AS RecordType
FROM eda.Customer c
INNER JOIN eda.CustomerAddress ca 
    ON c.CustLastName = ca.CustLastName
    AND c.CustFirstName = ca.CustFirstName
    AND c.CustMiddleInitial = ca.CustMiddleInitial
    AND c.CustSuffix = ca.CustSuffix
    AND c.CustDOB = ca.CustDOB
WHERE ca.CustState IS NOT NULL 
  AND LEN(ca.CustState) = 2  -- Ensure it's a valid 2-letter state code
  AND NOT EXISTS (
      SELECT 1 FROM integration.CustomerLocationBridge b
      WHERE b.CustomerKey = CONCAT(c.CustLastName, '|', c.CustFirstName, '|', c.CustMiddleInitial, '|', c.CustSuffix, '|', CONVERT(NVARCHAR(10), c.CustDOB, 120))
        AND b.StateCode = ca.CustState
        AND b.RecordType = N'Customer'
  );
GO

-- Load Account location data
-- Note: Uses eda schema prefix
INSERT INTO integration.CustomerLocationBridge (CustomerKey, AccountKey, StateCode, RecordType)
SELECT DISTINCT
    NULL AS CustomerKey,
    CONCAT(a.AccountName, '|', a.LocationAddress1, '|', a.LocationCity, '|', a.LocationState, '|', a.LocationZip, '|', a.CompanyCode) AS AccountKey,
    a.LocationState AS StateCode,  -- This should be 2-letter state code
    N'Account' AS RecordType
FROM eda.Account a
WHERE a.LocationState IS NOT NULL 
  AND LEN(a.LocationState) = 2  -- Ensure it's a valid 2-letter state code
  AND NOT EXISTS (
      SELECT 1 FROM integration.CustomerLocationBridge b
      WHERE b.AccountKey = CONCAT(a.AccountName, '|', a.LocationAddress1, '|', a.LocationCity, '|', a.LocationState, '|', a.LocationZip, '|', a.CompanyCode)
        AND b.StateCode = a.LocationState
        AND b.RecordType = N'Account'
  );
GO

-- Verify bridge table population
SELECT 
    RecordType,
    COUNT(*) AS RecordCount,
    COUNT(DISTINCT StateCode) AS UniqueStates
FROM integration.CustomerLocationBridge
GROUP BY RecordType;
GO


-- =====================================================================
-- STEP 2: Create Unified Location Dimension View
-- 步骤 2: 创建统一的地理维度视图
--
-- PURPOSE / 目的:
-- Join the dw.DimLocations with our bridge table to create
-- a unified geographic dimension with customer/account associations.
-- 将 dw.DimLocations 与桥梁表连接，创建包含客户/账户关联的统一地理维度。
-- =====================================================================

-- Drop and recreate view
IF OBJECT_ID('integration.vw_UnifiedLocationDim', 'V') IS NOT NULL
    DROP VIEW integration.vw_UnifiedLocationDim;
GO

CREATE VIEW integration.vw_UnifiedLocationDim AS
SELECT
    dl.LocationID,
    dl.LocationAbbr,
    dl.LocationDesc,
    dl.LocationType,
    dl.Geolocation,
    b.BridgeID,
    b.CustomerKey,
    b.AccountKey,
    b.StateCode,
    b.RecordType,
    b.LastUpdated
FROM dw.DimLocations dl
INNER JOIN integration.CustomerLocationBridge b 
    ON dl.LocationAbbr = b.StateCode;  -- Join on state abbreviation
GO


-- =====================================================================
-- STEP 3: Create Final Analysis View (Wide Table for BI)
-- 步骤 3: 创建最终分析视图 (BI 大宽表)
--
-- PURPOSE / 目的:
-- Create a comprehensive view that combines customer/account data
-- with chronic disease health indicators for easy BI analysis.
-- 创建综合视图，将客户/账户数据与慢性病健康指标结合，便于 BI 分析。
-- =====================================================================

IF OBJECT_ID('integration.vw_CustomerHealthRiskAnalysis', 'V') IS NOT NULL
    DROP VIEW integration.vw_CustomerHealthRiskAnalysis;
GO

CREATE VIEW integration.vw_CustomerHealthRiskAnalysis AS
SELECT
    -- Bridge/Location Info
    loc.BridgeID,
    loc.RecordType,
    loc.StateCode,
    loc.LocationAbbr,
    loc.LocationDesc AS StateName,
    loc.Geolocation,
    
    -- Customer Info (if RecordType = 'Customer')
    loc.CustomerKey,
    cust.CustFirstName,
    cust.CustLastName,
    cust.CustMiddleInitial,
    cust.CustSuffix,
    cust.CustDOB,
    cust.Gender AS CustomerGender,
    
    -- Account Info (if RecordType = 'Account')
    loc.AccountKey,
    acct.AccountName,
    acct.LocationCity AS AccountCity,
    acct.LocationZip AS AccountZip,
    acct.NumberOfEmployees,
    acct.CompanyCode,
    
    -- Health Observation Info
    obs.ObservationID,
    obs.YearStart,
    obs.YearEnd,
    obs.DataValue,
    obs.LowConfidenceLimit,
    obs.HighConfidenceLimit,
    obs.DataValueFootnote,
    obs.DataSource,
    
    -- Topic Info
    t.TopicID,
    t.TopicName,
    t.TopicCode,
    
    -- Question Info
    q.QuestionID,
    q.QuestionText,
    q.QuestionCode,
    
    -- Stratification Info
    s.StratificationID,
    s.StratificationValue,
    sc.StratifCategoryID,
    sc.CategoryName AS StratificationCategory,
    
    -- Data Value Type Info
    dvt.DataValueTypeID,
    dvt.TypeName AS DataValueType,
    dvt.UnitOfMeasure

FROM integration.vw_UnifiedLocationDim loc

-- Join with Health Observations (Fact Table)
INNER JOIN dw.FactHealthObservations obs
    ON loc.LocationID = obs.LocationID

-- Join with Dimension Tables
LEFT JOIN dw.DimTopics t
    ON obs.TopicID = t.TopicID
LEFT JOIN dw.DimQuestions q
    ON obs.QuestionID = q.QuestionID
LEFT JOIN dw.DimStratifications s
    ON obs.StratificationID = s.StratificationID
LEFT JOIN dw.DimStratificationCategories sc
    ON s.StratifCategoryID = sc.StratifCategoryID
LEFT JOIN dw.DimDataValueTypes dvt
    ON obs.DataValueTypeID = dvt.DataValueTypeID

-- Join with Customer (only when RecordType = 'Customer')
LEFT JOIN eda.Customer cust
    ON loc.RecordType = N'Customer'
    AND loc.CustomerKey = CONCAT(cust.CustLastName, '|', cust.CustFirstName, '|', cust.CustMiddleInitial, '|', cust.CustSuffix, '|', CONVERT(NVARCHAR(10), cust.CustDOB, 120))

-- Join with Account (only when RecordType = 'Account')
LEFT JOIN eda.Account acct
    ON loc.RecordType = N'Account'
    AND loc.AccountKey = CONCAT(acct.AccountName, '|', acct.LocationAddress1, '|', acct.LocationCity, '|', acct.LocationState, '|', acct.LocationZip, '|', acct.CompanyCode);
GO


-- =====================================================================
-- STEP 4: Example Queries / 查询示例
-- =====================================================================

-- Query 1: Average health indicators for customers in California (CA)
-- 查询 1: 查看加州 (CA) 客户的平均健康指标
SELECT
    StateName,
    TopicName,
    AVG(DataValue) AS AverageIndicatorValue,
    COUNT(*) AS ObservationCount
FROM integration.vw_CustomerHealthRiskAnalysis
WHERE StateCode = 'CA'
  AND RecordType = N'Customer'
  AND DataValue IS NOT NULL
GROUP BY StateName, TopicName
ORDER BY TopicName;
GO

-- Query 2: Top 5 states with highest diabetes rates and our account counts
-- 查询 2: 糖尿病指标最高的五个州及我们的企业账户数量
WITH DiabetesStats AS (
    SELECT
        StateCode,
        StateName,
        AccountKey,
        AVG(DataValue) AS AvgDiabetesRate
    FROM integration.vw_CustomerHealthRiskAnalysis
    WHERE TopicName LIKE '%Diabetes%'
      AND RecordType = N'Account'
      AND DataValue IS NOT NULL
    GROUP BY StateCode, StateName, AccountKey
)
SELECT TOP 5
    StateName,
    COUNT(DISTINCT AccountKey) AS NumberOfAccounts,
    AVG(AvgDiabetesRate) AS AvgStateDiabetesRate
FROM DiabetesStats
GROUP BY StateName
ORDER BY AvgStateDiabetesRate DESC;
GO

-- Query 3: Customer count and obesity indicators by state
-- 查询 3: 各州客户总数及肥胖问题平均指标
SELECT
    StateName,
    COUNT(DISTINCT CustomerKey) AS TotalCustomers,
    AVG(CASE WHEN TopicName LIKE '%Obesity%' THEN DataValue ELSE NULL END) AS AvgObesityIndicator,
    MIN(YearStart) AS EarliestYear,
    MAX(YearEnd) AS LatestYear
FROM integration.vw_CustomerHealthRiskAnalysis
WHERE RecordType = N'Customer'
GROUP BY StateName
HAVING COUNT(DISTINCT CustomerKey) > 0
ORDER BY TotalCustomers DESC;
GO

-- Query 4: Detailed health risk profile for a specific state
-- 查询 4: 特定州的详细健康风险概况
SELECT
    TopicName,
    QuestionText,
    DataValueType,
    AVG(DataValue) AS AvgValue,
    MIN(DataValue) AS MinValue,
    MAX(DataValue) AS MaxValue,
    COUNT(*) AS MeasurementCount
FROM integration.vw_CustomerHealthRiskAnalysis
WHERE StateCode = 'NY'
  AND YearStart >= 2020
  AND DataValue IS NOT NULL
GROUP BY TopicName, QuestionText, DataValueType
ORDER BY TopicName, AvgValue DESC;
GO


-- =====================================================================
-- IMPLEMENTATION NOTES / 实施说明
-- =====================================================================
-- 
-- 1. DATABASE SCHEMA / 数据库架构:
--    This script assumes both 'eda' and 'dw' schemas exist in the same database.
--    If they are in different databases, you'll need to use three-part naming
--    (DatabaseName.SchemaName.ObjectName) or Elastic Query.
--    此脚本假设 'eda' 和 'dw' 架构在同一数据库中。
--    如果在不同数据库，需要使用三段式命名或 Elastic Query。
--
-- 2. PERMISSIONS / 权限:
--    Ensure the executing user has permissions to:
--    - CREATE SCHEMA, CREATE TABLE, CREATE VIEW
--    - SELECT on eda.* and dw.* tables
--    确保执行用户有权限创建架构/表/视图，以及查询 eda.* 和 dw.* 表
--
-- 3. ETL SCHEDULING / ETL 调度:
--    The INSERT statements in Step 1.1 should be scheduled as a regular
--    ETL job (e.g., daily or weekly using Azure Data Factory, SQL Agent, 
--    or Azure Functions) to keep the bridge table synchronized with
--    source data changes.
--    步骤 1.1 的 INSERT 语句应配置为定期 ETL 作业（使用 Azure Data Factory、
--    SQL Agent 或 Azure Functions），以保持桥梁表与源数据同步。
--
-- 4. STATE CODE MAPPING / 州代码映射:
--    Ensure that:
--    - eda.CustomerAddress.CustState contains 2-letter state codes (e.g., 'CA', 'NY')
--    - eda.Account.LocationState contains 2-letter state codes
--    - dw.DimLocations.LocationAbbr contains matching state codes
--    确保客户地址、账户位置、健康数据位置维度都使用一致的两字母州代码。
--
-- 5. PERFORMANCE OPTIMIZATION / 性能优化:
--    - Bridge table indexes are created for common join columns
--    - Consider partitioning FactHealthObservations by YearStart for large datasets
--    - Monitor query performance and add additional indexes as needed
--    已为常用连接列创建索引；对于大数据集考虑对事实表按年份分区；
--    监控查询性能并根据需要添加索引。
--
-- 6. FIELD LENGTH CONSISTENCY / 字段长度一致性:
--    All field lengths have been aligned with EDA_AzureSQL.sql:
--    - Customer names: VARCHAR(100)
--    - Account names: VARCHAR(80)
--    - LocationCity: VARCHAR(60)
--    - LocationState: VARCHAR(50)
--    所有字段长度已与 EDA_AzureSQL.sql 保持一致。
--
-- =====================================================================
