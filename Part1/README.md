# Database Schema Enhancement Project

## Project Overview

## SQL Reserved Words Handling

To ensure compatibility with ERwin and various SQL database systems, we've taken the following approach to handle SQL reserved words in our schema:

### Reserved Words Modified

We've identified and renamed the following SQL reserved words to avoid potential conflicts:

| Original Name | New Name      | Reason for Change |
|---------------|---------------|-------------------|
| `Definition`  | `DefinitionText` | Avoids conflict with SQL reserved word |
| `Role`        | `RoleType`    | Avoids conflict with SQL reserved word |
| `Description` | `DescriptionText` | Avoids conflict with SQL reserved word |
| `Criteria`    | `CriteriaText` | Avoids conflict with SQL reserved word |
| `Threshold`   | `ThresholdValue` | Avoids conflict with SQL reserved word |
| `Level`       | `LevelNum`    | Avoids conflict with SQL reserved word |
| `ASC`         | `ASC_Table`   | Avoids conflict with SQL ORDER BY clause |

### Implementation Approach

1. **Consistent Naming**: All renamed columns follow a consistent naming pattern (appending 'Text' or 'Type' as appropriate)
2. **Foreign Key Updates**: All related foreign key constraints have been updated to reference the new column names
3. **Documentation**: This documentation serves as a reference for developers to understand the naming conventions used
4. **ERwin Compatibility**: These changes ensure better compatibility with ERwin data modeling tools

### Example Changes

```sql
-- Before
CREATE TABLE SomeTable (
    ID INT PRIMARY KEY,
    [Description] TEXT,
    [Level] INT
);

-- After
CREATE TABLE SomeTable (
    ID INT PRIMARY KEY,
    DescriptionText TEXT,
    LevelNum INT
);
```

## Project Overview

This project enhances the database schema based on business cases from the EDA Project Support Material to support complex business scenarios. The project addresses multiple key many-to-many relationships and business rules in the insurance industry.

---

## Case Study Solutions

### Case 1: Account to BillingAccount Many-to-Many Relationship

#### Business Scenario
**WalMart Columbus Multiple Billing Address Scenario**

WalMart Columbus uses 3 different PO boxes to receive different types of invoices:
- FSA (Flexible Spending Account) invoices
- Life insurance invoices
- A&H (Accident & Health) insurance invoices

Additionally, these invoices need to distinguish between employee types:
- **Salaried employees**
- **Hourly employees**

#### Data Model Problem
The original `Account_BillingAccount` junction table cannot distinguish employee type differences when the same account uses different billing addresses.

#### Solution
Add an `EmployeeType` field to the `Account_BillingAccount` table:

```sql
ALTER TABLE Account_BillingAccount
ADD COLUMN EmployeeType VARCHAR(8) CHECK (EmployeeType IN ('salaried', 'hourly'));
```

#### Implementation Details
- **Field Name**: `EmployeeType`
- **Data Type**: `VARCHAR(8)`
- **Constraint**: `CHECK` constraint, only allows `'salaried'` or `'hourly'` values
- **Business Purpose**: Allows the same Account to establish multiple relationships with the same BillingAccount, each corresponding to a different employee type

#### Usage Example
```sql
-- WalMart Columbus FSA invoice configuration
INSERT INTO Account_BillingAccount (
    AccountName, LocationAddress1, LocationCity, LocationState, LocationZip, CompanyCode,
    BAccName, BillingAddress1, BillingCity, BillingState, BillingZip,
    RelationshipType, StartDate, EmployeeType
) VALUES 
    ('WalMart', '123 Main St', 'Columbus', 'OH', '43215', 'WM',
     'WalMart FSA Billing', 'PO Box 1001', 'Columbus', 'OH', '43216',
     'FSA_Billing', '2024-01-01', 'salaried'),
    ('WalMart', '123 Main St', 'Columbus', 'OH', '43215', 'WM',
     'WalMart FSA Billing', 'PO Box 1002', 'Columbus', 'OH', '43216',
     'FSA_Billing', '2024-01-01', 'hourly');
```

---

### Case 2: Associate to ManagerContract One-to-Many Relationship

#### Business Scenario
**Associate's Multiple Writing Numbers and SitCode Management**

A company Associate (agent) can have multiple Writing Numbers, each authorized by a specific state's Department of Insurance (State DOI). Each Writing Number can have multiple SitCodes (i.e., ManagerContracts) for conducting new business.

**SitCode Types**:
- **SitCode0** (Primary SitCode): Represents the Associate's formal reporting chain within the company
  - Defines the Associate's official upline: DSC (District Sales Coordinator), RSC (Regional Sales Coordinator), SSC (State Sales Coordinator), TD (Territory Director)
  
- **Other SitCodes** (Secondary SitCodes): Represent "side deals" where the Associate conducts business outside their SitCode0's jurisdiction

#### Real-World Example
**Keith's Cross-State Business Scenario**:

1. **Keith's Primary Business** (SitCode0):
   - Upline chain: Cliff (DSC) → Rob (RSC) → David (SSC) → Gerald (TD)
   - David's state operation area: Georgia (GA)

2. **Keith's Side Business** (SitCodeA):
   - Keith obtained a sales license in Alabama (AL)
   - Keith made a side deal with Jim in AL
   - New upline chain: Jim (DSC) → Ken (RSC) → Pat (SSC) → Gerald (TD)

#### Data Model Problem
The original `ManagerContract` table cannot distinguish between primary SitCode and side business SitCode.

#### Solution
Add a `SitCodeType` field to the `ManagerContract` table:

```sql
ALTER TABLE ManagerContract
ADD COLUMN SitCodeType TINYINT(1) CHECK (SitCodeType IN (0, 1));
```

#### Implementation Details
- **Field Name**: `SitCodeType`
- **Data Type**: `TINYINT(1)`
- **Constraint**: `CHECK` constraint, only allows `0` or `1` values
  - `0` = Primary SitCode (SitCode0), represents formal reporting chain
  - `1` = Side business SitCode, represents cross-regional business agreement
- **Business Purpose**: Identifies the Associate's business relationship type, supporting cross-state sales and multiple management structures

#### Usage Example
```sql
-- Keith's primary SitCode (in Georgia)
INSERT INTO ManagerContract (
    SitCode, SitCodeType, CompanyCode, WritingNumber, Level, IssueDate,
    ContractType, TerritoryName, StateOperationName, StateCode,
    AssocLastName, AssocFirstName, AssocMiddleInitial, AssocSuffix, AssocDOB
) VALUES (
    'KEITH-GA-001', 0, 'ABC', 'WN12345', 3, '2023-01-01',
    'Standard', 'Southeast', 'Georgia Operations', 'GA',
    'Smith', 'Keith', 'J', 'Jr', '1980-05-15'
);

-- Keith's side business SitCode (in Alabama)
INSERT INTO ManagerContract (
    SitCode, SitCodeType, CompanyCode, WritingNumber, Level, IssueDate,
    ContractType, TerritoryName, StateOperationName, StateCode,
    AssocLastName, AssocFirstName, AssocMiddleInitial, AssocSuffix, AssocDOB
) VALUES (
    'KEITH-AL-001', 1, 'ABC', 'WN12346', 3, '2023-06-01',
    'Side_Deal', 'Southeast', 'Alabama Operations', 'AL',
    'Smith', 'Keith', 'J', 'Jr', '1980-05-15'
);
```

---

### Case 3: Customer Many-to-Many Relationship Complex Scenarios

This section addresses multiple many-to-many relationships between the Customer entity and other entities, which are very common in the insurance business.

#### Case 3: Customer (n..n) Customer - Family Relationships

**Business Scenario: Daddy Warbucks' Family Policy**

Daddy Warbucks purchases health insurance for his son and family. He establishes a trust fund to pay for the policy and purchases a dread disease rider specifically for his son.

**Data Model Problem**:
- Need to record relationships between customers (parent-child, spouse, etc.)
- The existing `CustomerRelation` table can handle this situation

**Solution**:
Use the existing `CustomerRelation` table, which already supports many-to-many relationships between customers.

```sql
-- Example: Record the relationship between Daddy Warbucks and his son
INSERT INTO CustomerRelation (
    CustLastName, CustFirstName, CustMiddleInitial, CustSuffix, CustDOB,
    RelationLastName, RelationFirstName, RelationMiddleInitial, RelationSuffix, RelationDOB,
    RelationToCustomer, StartDate
) VALUES (
    'Warbucks', 'Daddy', 'D', '', '1960-01-01',
    'Warbucks', 'Junior', 'J', '', '1990-05-15',
    'Father-Son', '1990-05-15'
);
```

---

### Case 4: Customer (n..n) Contract - Multiple Roles in Contracts

**Business Scenario: Complex Policy Relationships**

In Daddy Warbucks' case:
- **Policy Owner**: Daddy Warbucks
- **Policy Payer**: Warbucks Family Trust Fund
- **Insured**: Son and his family
- Daddy also has his own life insurance policy

**Data Model Problem**:
A simple Customer-Contract junction table cannot distinguish the different roles customers play in a contract.

**Solution**:
Create a `ContractingParty` table to explicitly define each customer's role in a contract.

First, ensure the role definition table exists:
```sql
CREATE TABLE ContractingPartyRole (
  Role VARCHAR(100) NOT NULL,
  Description TEXT,
  CONSTRAINT PK_ContractingPartyRole PRIMARY KEY (Role)
);

-- Insert common roles
INSERT INTO ContractingPartyRole (Role, Description) VALUES
  ('Owner', 'Policy Owner'),
  ('Payer', 'Policy Payer'),
  ('Insured', 'Insured Party'),
  ('Beneficiary', 'Beneficiary');
```

Then create the junction table:
```sql
CREATE TABLE ContractingParty (
  ContractNumber VARCHAR(100) NOT NULL,
  LineOfBusiness VARCHAR(100) NOT NULL,
  SeriesName VARCHAR(100) NOT NULL,
  PlanName VARCHAR(100) NOT NULL,
  CustLastName VARCHAR(100) NOT NULL,
  CustFirstName VARCHAR(100) NOT NULL,
  CustMiddleInitial CHAR(1) NOT NULL,
  CustSuffix VARCHAR(10) NOT NULL,
  CustDOB DATE NOT NULL,
  Role VARCHAR(100) NOT NULL,
  CONSTRAINT PK_ContractingParty PRIMARY KEY (
    ContractNumber, LineOfBusiness, SeriesName, PlanName, 
    CustLastName, CustFirstName, CustDOB, Role
  ),
  CONSTRAINT FK_ContractingParty_Contract FOREIGN KEY (
    ContractNumber, LineOfBusiness, SeriesName, PlanName
  ) REFERENCES Contract(ContractNumber, LineOfBusiness, SeriesName, PlanName),
  CONSTRAINT FK_ContractingParty_Customer FOREIGN KEY (
    CustLastName, CustFirstName, CustMiddleInitial, CustSuffix, CustDOB
  ) REFERENCES Customer(CustLastName, CustFirstName, CustMiddleInitial, CustSuffix, CustDOB),
  CONSTRAINT FK_ContractingParty_Role FOREIGN KEY (Role)
    REFERENCES ContractingPartyRole(Role)
);
```

**Usage Example**:
```sql
-- Daddy Warbucks' health insurance contract
INSERT INTO ContractingParty VALUES
  ('HC001', 'Health', 'Family', 'Premium', 'Warbucks', 'Daddy', 'D', '', '1960-01-01', 'Owner'),
  ('HC001', 'Health', 'Family', 'Premium', 'Warbucks Trust', '', '', '', '1950-01-01', 'Payer'),
  ('HC001', 'Health', 'Family', 'Premium', 'Warbucks', 'Junior', 'J', '', '1990-05-15', 'Insured');

-- Daddy's life insurance
INSERT INTO ContractingParty VALUES
  ('LC001', 'Life', 'Standard', 'Term', 'Warbucks', 'Daddy', 'D', '', '1960-01-01', 'Owner'),
  ('LC001', 'Life', 'Standard', 'Term', 'Warbucks', 'Daddy', 'D', '', '1960-01-01', 'Insured');
```

---

### Case 5: Customer (n..n) ContractBenefit - Specific Benefit Recipients

**Business Scenario: Daddy Warbucks' Complex Insurance Arrangements**

- **Daddy Warbucks' health insurance policy**: Covers his son and family as beneficiaries
- **His son also carries the company's accident insurance**: For himself and his family

**Data Model Problem**:
Need to designate specific customers as beneficiaries of specific benefits (Riders), not just the entire contract.

**Related Modules of the Model**:
```
Customer -(1,N)- ContractingPartyInRole -(N,1)- Contract-h -(1,N)- ContractBenefit
    |
  (N,1)
    |
ContractingPartyRole
```

This module builds the Customer (N,N) ContractBenefit relationship.

**Solution**:
Add a parameter in `ContractingPartyRole` to flag whether this customer is enrolled as a beneficiary in the specific contract and policies. Since customer and contract are (N,N) through `ContractingPartyRole`, for each contract, there are possibly many benefits, and thus multiple `ContractBenefit`. This creates an (N,N) relationship between Customer and ContractBenefit. A Customer can be linked to multiple ContractBenefits through different ContractingPartyRoles across various contracts.

**Implementation**:
```sql
-- Modify ContractingPartyRole to include beneficiary flag
ALTER TABLE ContractingPartyRole
ADD COLUMN IsBeneficiary BOOLEAN DEFAULT FALSE;

-- The existing ContractingParty table already supports the relationship
-- No additional tables needed
```

**Usage Example**:
```sql
-- Define beneficiary role
INSERT INTO ContractingPartyRole (RoleType, DescriptionText, IsBeneficiary) VALUES
  ('Beneficiary', 'Policy Beneficiary', TRUE),
  ('Owner', 'Policy Owner', FALSE),
  ('Insured', 'Insured Party', FALSE);

-- Daddy Warbucks' health insurance: his son and family as beneficiaries
INSERT INTO ContractingParty VALUES
  ('HC001', 'Health', 'Family', 'Premium', 'Warbucks', 'Junior', 'J', '', '1990-05-15', 'Beneficiary'),
  ('HC001', 'Health', 'Family', 'Premium', 'Warbucks', 'Jane', 'M', '', '1992-03-20', 'Beneficiary'),
  ('HC001', 'Health', 'Family', 'Premium', 'Warbucks', 'Daddy', 'D', '', '1960-01-01', 'Owner');

-- His son's accident insurance for himself and his family
INSERT INTO ContractingParty VALUES
  ('AC001', 'Accident', 'Standard', 'Basic', 'Warbucks', 'Junior', 'J', '', '1990-05-15', 'Owner'),
  ('AC001', 'Accident', 'Standard', 'Basic', 'Warbucks', 'Junior', 'J', '', '1990-05-15', 'Beneficiary'),
  ('AC001', 'Accident', 'Standard', 'Basic', 'Warbucks', 'Jane', 'M', '', '1992-03-20', 'Beneficiary');
```

---

### Case 6: Customer (n..n) Account - Multiple Employment Relationships

**Business Scenario: Keith's Multiple Jobs**

Dana's Dry Cleaning has many employees, including Keith. Keith can work at Dana's Dry Cleaning and moonlight at Scott's Garage simultaneously.

**Data Model Problem**:
A customer can be an employee at multiple accounts (employers) at the same time.

**Solution**:
No changes needed. The existing `Account_Member` table already perfectly supports this scenario.

```sql
-- Keith works at Dana's Dry Cleaning
INSERT INTO Account_Member (
    AccountName, LocationAddress1, LocationCity, LocationState, LocationZip,
    CustLastName, CustFirstName, CustMiddleInitial, CustDOB, StartDate,
    CustSuffix, CompanyCode
) VALUES (
    'Dana Dry Cleaning', '100 Main St', 'Springfield', 'IL', '62701',
    'Smith', 'Keith', 'J', '1985-07-20', '2020-01-15',
    'Jr', 'DDC'
);

-- Keith moonlights at Scott's Garage
INSERT INTO Account_Member (
    AccountName, LocationAddress1, LocationCity, LocationState, LocationZip,
    CustLastName, CustFirstName, CustMiddleInitial, CustDOB, StartDate,
    CustSuffix, CompanyCode
) VALUES (
    'Scott Garage', '200 Oak Ave', 'Springfield', 'IL', '62702',
    'Smith', 'Keith', 'J', '1985-07-20', '2021-06-01',
    'Jr', 'SG'
);
```

---

### Case 7: Customer (n..n) Associate - Commission Bequests

**Business Scenario: Walt and Dave's Commission Inheritance**

- **Walt**, a long-standing sales associate of the company, passes away bequeathing his commissions to his wife and son
- **Dave**, another long-standing company sales associate and friend of Walt's family, also passes away bequeathing his commissions to Walt's son

**Related Modules of the Model**:
The relationship is built through three chained modules:

1. **Customer (N,N) ContractPremium relationship**:
   ```
   Customer (N,N) Contract-h -(1,N)- ContractBenefit -(1,N)- ContractPremium
   ```
   (same as case 5)

2. **ContractPremium (N,N) ManagerContract relationship**:
   ```
   ContractPremium -(1,N)- Premium_MgmtContract -(N,1)- ManagerContract
   ```

3. **ManagerContract (N,1) Associate relationship**:
   ```
   ManagerContract (N,1) Associate
   ```
   (same as case 2)

**Data Model Problem**:
Each associate can have multiple commissions (`Premium_MgmtContract`) through the contracts they belong to. All commissions will be divided or distributed to some beneficiaries, and the beneficiaries are a specific kind of customer, with the type or role stored in the `ContractingPartyRole`. 

Usually, the beneficiaries are the associates themselves as the customer who receives commission. But in the case provided, the associates that passed away will have their commissions updated or redirected to new beneficiaries (e.g., family members) who will be recorded as new Customer entries in the model, and then receive the commission from the associates.

**Solution**:
Create an `AssociateBeneficiary` table to manage these beneficiary designations and commission inheritance.

```sql
CREATE TABLE AssociateBeneficiary (
  -- Associate who is bequeathing
  AssocLastName VARCHAR(100) NOT NULL,
  AssocFirstName VARCHAR(100) NOT NULL,
  AssocMiddleInitial CHAR(1) NOT NULL,
  AssocSuffix VARCHAR(10) NOT NULL,
  AssocDOB DATE NOT NULL,
  -- Customer who is the beneficiary
  CustLastName VARCHAR(100) NOT NULL,
  CustFirstName VARCHAR(100) NOT NULL,
  CustMiddleInitial CHAR(1) NOT NULL,
  CustSuffix VARCHAR(10) NOT NULL,
  CustDOB DATE NOT NULL,
  -- Additional Details
  DesignationType VARCHAR(50), -- e.g., 'Bequest', 'Commission Split'
  Percentage DECIMAL(5, 2),    -- Benefit percentage
  EffectiveDate DATE,           -- Effective date
  CONSTRAINT PK_AssociateBeneficiary PRIMARY KEY (
    AssocLastName, AssocFirstName, AssocDOB, 
    CustLastName, CustFirstName, CustDOB
  ),
  CONSTRAINT FK_AssociateBeneficiary_Associate FOREIGN KEY (
    AssocLastName, AssocFirstName, AssocMiddleInitial, AssocSuffix, AssocDOB
  ) REFERENCES Associate(AssocLastName, AssocFirstName, AssocMiddleInitial, AssocSuffix, AssocDOB),
  CONSTRAINT FK_AssociateBeneficiary_Customer FOREIGN KEY (
    CustLastName, CustFirstName, CustMiddleInitial, CustSuffix, CustDOB
  ) REFERENCES Customer(CustLastName, CustFirstName, CustMiddleInitial, CustSuffix, CustDOB)
);
```

**Usage Example**:
```sql
-- Walt bequeaths commissions to his wife (50%) and son (50%)
INSERT INTO AssociateBeneficiary VALUES
  ('Johnson', 'Walt', 'W', '', '1950-03-10',
   'Johnson', 'Mary', 'M', '', '1952-06-15',
   'Bequest', 50.00, '2024-01-15'),
  ('Johnson', 'Walt', 'W', '', '1950-03-10',
   'Johnson', 'Tom', 'T', 'Jr', '1980-09-20',
   'Bequest', 50.00, '2024-01-15');

-- Dave bequeaths commissions to Walt's son (100%)
INSERT INTO AssociateBeneficiary VALUES
  ('Smith', 'Dave', 'D', '', '1948-11-05',
   'Johnson', 'Tom', 'T', 'Jr', '1980-09-20',
   'Bequest', 100.00, '2024-02-20');
```

---

## Database Modification Summary

### Modified and New Tables

#### Field Modifications
1. **Account_BillingAccount**
   - New field: `EmployeeType VARCHAR(8)`
   - Constraint: `CHECK (EmployeeType IN ('salaried', 'hourly'))`
   - Purpose: Distinguish billing relationships for salaried vs. hourly employees

2. **ManagerContract**
   - New field: `SitCodeType TINYINT(1)`
   - Constraint: `CHECK (SitCodeType IN (0, 1))`
   - Purpose: Distinguish primary business (0) from side business (1)

#### New Tables
3. **ContractingPartyRole**
   - Defines role types for customers in contracts
   - Roles include: Owner, Payer, Insured, Beneficiary
   - New field: `IsBeneficiary BOOLEAN` - Flags whether this role represents a beneficiary in the contract

4. **ContractingParty**
   - Links Customer and Contract, explicitly defining customer roles in contracts
   - Supports one contract with multiple customers, each playing different roles
   - Through ContractingPartyRole, enables Customer (N,N) ContractBenefit relationship

5. **AssociateBeneficiary**
   - Links Associate and Customer
   - Manages commission bequests or splits from associates to customers
   - Includes percentage and effective date details

---

## File Descriptions

- **Accounttable.sql**: Complete database DDL script containing all table definitions and constraints
- **README.md**: This document, explaining business cases and database enhancement solutions

---

## Author and Maintenance

This project is developed based on business requirements from the EDA Project Support Material.

**Last Updated**: October 2025
