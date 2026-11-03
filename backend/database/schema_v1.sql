SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE TABLE schema_metadata (
  version_no INT PRIMARY KEY,
  dataset_name VARCHAR(80) NOT NULL,
  random_seed INT NOT NULL,
  as_of_date DATE NOT NULL,
  seeded_at_utc DATETIME(6) NULL,
  seed_status ENUM('SCHEMA_READY','COMPLETE') NOT NULL
) ENGINE=InnoDB COMMENT='Version and reproducibility metadata for the synthetic demo';

CREATE TABLE regions (
  region_id SMALLINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  region_code VARCHAR(12) NOT NULL UNIQUE,
  region_name VARCHAR(80) NOT NULL,
  division_name VARCHAR(60) NOT NULL,
  status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE'
) ENGINE=InnoDB COMMENT='Top-level operating regions';

CREATE TABLE areas (
  area_id SMALLINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  region_id SMALLINT UNSIGNED NOT NULL,
  area_code VARCHAR(12) NOT NULL UNIQUE,
  area_name VARCHAR(80) NOT NULL,
  district_name VARCHAR(60) NOT NULL,
  status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  CONSTRAINT fk_area_region FOREIGN KEY (region_id) REFERENCES regions(region_id)
) ENGINE=InnoDB COMMENT='Microfinance operating areas within regions';

CREATE TABLE branches (
  branch_id SMALLINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  area_id SMALLINT UNSIGNED NOT NULL,
  branch_code VARCHAR(12) NOT NULL UNIQUE,
  branch_name VARCHAR(100) NOT NULL,
  division_name VARCHAR(60) NOT NULL,
  district_name VARCHAR(60) NOT NULL,
  upazila_name VARCHAR(60) NOT NULL,
  opening_date DATE NOT NULL,
  status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  CONSTRAINT fk_branch_area FOREIGN KEY (area_id) REFERENCES areas(area_id),
  INDEX ix_branch_geo (division_name, district_name, upazila_name)
) ENGINE=InnoDB COMMENT='Service branches and geographic reporting dimensions';

CREATE TABLE staff (
  staff_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  employee_number VARCHAR(20) NOT NULL UNIQUE,
  branch_id SMALLINT UNSIGNED NOT NULL,
  full_name VARCHAR(100) NOT NULL,
  role_name ENUM('BRANCH_MANAGER','CREDIT_OFFICER','COLLECTION_OFFICER','KYC_OFFICER','CASHIER') NOT NULL,
  supervisor_id INT UNSIGNED NULL,
  employment_date DATE NOT NULL,
  exit_date DATE NULL,
  status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  CONSTRAINT fk_staff_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_staff_supervisor FOREIGN KEY (supervisor_id) REFERENCES staff(staff_id),
  INDEX ix_staff_branch_role (branch_id, role_name)
) ENGINE=InnoDB COMMENT='Synthetic branch personnel and reporting lines';

CREATE TABLE village_organizations (
  vo_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  branch_id SMALLINT UNSIGNED NOT NULL,
  vo_code VARCHAR(20) NOT NULL UNIQUE,
  vo_name VARCHAR(100) NOT NULL,
  village_name VARCHAR(80) NOT NULL,
  meeting_frequency ENUM('WEEKLY','MONTHLY') NOT NULL,
  meeting_day TINYINT UNSIGNED NOT NULL COMMENT 'ISO weekday, Monday=1',
  responsible_officer_id INT UNSIGNED NOT NULL,
  formed_date DATE NOT NULL,
  status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  CONSTRAINT fk_vo_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_vo_officer FOREIGN KEY (responsible_officer_id) REFERENCES staff(staff_id),
  INDEX ix_vo_branch (branch_id, status)
) ENGINE=InnoDB COMMENT='Village organisations used for Dabi-style group services';

CREATE TABLE member_enrollments (
  enrollment_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  application_number VARCHAR(24) NOT NULL UNIQUE,
  application_date DATE NOT NULL,
  application_source ENUM('BRANCH','FIELD_APP','REFERRAL') NOT NULL,
  branch_id SMALLINT UNSIGNED NOT NULL,
  vo_id INT UNSIGNED NULL,
  requested_member_type ENUM('GROUP','INDIVIDUAL') NOT NULL,
  verification_status ENUM('PENDING','VERIFIED','FAILED') NOT NULL,
  status ENUM('PENDING','APPROVED','REJECTED','CANCELLED') NOT NULL,
  verified_by INT UNSIGNED NULL,
  approved_by INT UNSIGNED NULL,
  submitted_at_utc DATETIME(6) NOT NULL,
  decided_at_utc DATETIME(6) NULL,
  rejection_reason VARCHAR(160) NULL,
  CONSTRAINT fk_enroll_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_enroll_vo FOREIGN KEY (vo_id) REFERENCES village_organizations(vo_id),
  CONSTRAINT fk_enroll_verified FOREIGN KEY (verified_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_enroll_approved FOREIGN KEY (approved_by) REFERENCES staff(staff_id),
  INDEX ix_enroll_pipeline (status, application_date, branch_id)
) ENGINE=InnoDB COMMENT='Member application, verification, decision and turnaround workflow';

CREATE TABLE members (
  member_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  member_number VARCHAR(20) NOT NULL UNIQUE,
  enrollment_id INT UNSIGNED NOT NULL UNIQUE,
  branch_id SMALLINT UNSIGNED NOT NULL,
  vo_id INT UNSIGNED NULL,
  member_type ENUM('GROUP','INDIVIDUAL') NOT NULL,
  full_name VARCHAR(100) NOT NULL,
  gender ENUM('FEMALE','MALE','OTHER') NOT NULL,
  date_of_birth DATE NOT NULL,
  mobile_number VARCHAR(20) NOT NULL COMMENT 'Synthetic contact number',
  nid_masked_suffix CHAR(4) NOT NULL COMMENT 'Last four synthetic NID digits only',
  nid_sha256 CHAR(64) NOT NULL COMMENT 'SHA-256 of synthetic identifier; raw NID is never stored',
  marital_status ENUM('SINGLE','MARRIED','DIVORCED','WIDOWED') NOT NULL,
  education_level ENUM('NONE','PRIMARY','SECONDARY','HIGHER') NOT NULL,
  primary_livelihood VARCHAR(80) NOT NULL,
  household_size TINYINT UNSIGNED NOT NULL,
  household_earners TINYINT UNSIGNED NOT NULL,
  monthly_household_income DECIMAL(14,2) NOT NULL,
  monthly_household_expense DECIMAL(14,2) NOT NULL,
  poverty_score DECIMAL(5,2) NOT NULL COMMENT 'Demo vulnerability score from 0 to 100; higher means more vulnerable',
  vulnerable_household BOOLEAN NOT NULL,
  disability_indicator BOOLEAN NOT NULL,
  enrollment_date DATE NOT NULL,
  status ENUM('ACTIVE','SUSPENDED','EXITED') NOT NULL,
  exit_date DATE NULL,
  created_at_utc DATETIME(6) NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_member_enroll FOREIGN KEY (enrollment_id) REFERENCES member_enrollments(enrollment_id),
  CONSTRAINT fk_member_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_member_vo FOREIGN KEY (vo_id) REFERENCES village_organizations(vo_id),
  INDEX ix_member_reporting (branch_id, status, gender, member_type),
  INDEX ix_member_enrollment_date (enrollment_date)
) ENGINE=InnoDB COMMENT='Synthetic member master and socioeconomic reporting profile';

CREATE TABLE vo_memberships (
  vo_membership_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  member_id INT UNSIGNED NOT NULL,
  vo_id INT UNSIGNED NOT NULL,
  join_date DATE NOT NULL,
  exit_date DATE NULL,
  membership_status ENUM('ACTIVE','EXITED') NOT NULL,
  CONSTRAINT fk_vom_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_vom_vo FOREIGN KEY (vo_id) REFERENCES village_organizations(vo_id),
  INDEX ix_vom_vo_status (vo_id, membership_status)
) ENGINE=InnoDB COMMENT='Effective-dated membership of village organisations';

CREATE TABLE kyc_verifications (
  kyc_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  member_id INT UNSIGNED NOT NULL,
  document_type ENUM('NID_HASH','BIRTH_CERTIFICATE','PASSPORT') NOT NULL,
  verification_status ENUM('PENDING','VERIFIED','FAILED','EXPIRED') NOT NULL,
  verification_date DATE NULL,
  verified_by INT UNSIGNED NULL,
  aml_risk_category ENUM('LOW','MEDIUM','HIGH') NOT NULL,
  consent_status ENUM('GRANTED','WITHDRAWN','PENDING') NOT NULL,
  consent_date DATE NULL,
  next_review_date DATE NULL,
  created_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_kyc_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_kyc_staff FOREIGN KEY (verified_by) REFERENCES staff(staff_id),
  INDEX ix_kyc_status (verification_status, aml_risk_category, next_review_date)
) ENGINE=InnoDB COMMENT='KYC, AML risk and privacy-consent status without raw identity documents';

CREATE TABLE profile_update_requests (
  update_request_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  request_number VARCHAR(24) NOT NULL UNIQUE,
  member_id INT UNSIGNED NOT NULL,
  branch_id SMALLINT UNSIGNED NOT NULL,
  request_date DATE NOT NULL,
  request_source ENUM('BRANCH','FIELD_APP','CALL_CENTRE','MEMBER') NOT NULL,
  reason VARCHAR(160) NOT NULL,
  status ENUM('PENDING','APPROVED','REJECTED','CANCELLED') NOT NULL,
  reviewed_by INT UNSIGNED NULL,
  submitted_at_utc DATETIME(6) NOT NULL,
  decided_at_utc DATETIME(6) NULL,
  CONSTRAINT fk_profile_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_profile_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_profile_reviewer FOREIGN KEY (reviewed_by) REFERENCES staff(staff_id),
  INDEX ix_profile_pending (status, branch_id, request_date)
) ENGINE=InnoDB COMMENT='Auditable member profile-change workflow';

CREATE TABLE profile_update_details (
  update_detail_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  update_request_id INT UNSIGNED NOT NULL,
  field_name VARCHAR(64) NOT NULL,
  previous_value VARCHAR(255) NULL,
  new_value VARCHAR(255) NULL,
  CONSTRAINT fk_profile_detail FOREIGN KEY (update_request_id) REFERENCES profile_update_requests(update_request_id)
) ENGINE=InnoDB COMMENT='Field-level before and after values for profile updates';

CREATE TABLE member_status_history (
  member_status_history_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  member_id INT UNSIGNED NOT NULL,
  previous_status VARCHAR(20) NULL,
  new_status ENUM('ACTIVE','SUSPENDED','EXITED','TRANSFERRED') NOT NULL,
  effective_date DATE NOT NULL,
  reason VARCHAR(160) NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NULL,
  created_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_member_history FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_member_history_staff FOREIGN KEY (created_by) REFERENCES staff(staff_id),
  INDEX ix_member_history (member_id, effective_date)
) ENGINE=InnoDB COMMENT='Effective-dated member activation, suspension, transfer and exit events';

CREATE TABLE loan_products (
  product_id SMALLINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  product_code VARCHAR(16) NOT NULL UNIQUE,
  product_name VARCHAR(80) NOT NULL,
  lending_mode ENUM('GROUP','INDIVIDUAL') NOT NULL,
  eligible_member_type ENUM('GROUP','INDIVIDUAL','BOTH') NOT NULL,
  purpose_category VARCHAR(50) NOT NULL,
  minimum_amount DECIMAL(14,2) NOT NULL,
  maximum_amount DECIMAL(14,2) NOT NULL,
  default_term_months SMALLINT UNSIGNED NOT NULL,
  repayment_frequency ENUM('WEEKLY','MONTHLY') NOT NULL,
  grace_period_days SMALLINT UNSIGNED NOT NULL,
  service_charge_method ENUM('FLAT_DEMO','DECLINING_DEMO') NOT NULL,
  annual_service_charge_rate DECIMAL(7,4) NOT NULL COMMENT 'Synthetic demonstration rate, not an official BRAC rate',
  compulsory_savings_rate DECIMAL(7,4) NOT NULL,
  status ENUM('ACTIVE','INACTIVE') NOT NULL
) ENGINE=InnoDB COMMENT='Demonstration loan products; all parameters are synthetic';

CREATE TABLE loan_proposals (
  proposal_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  proposal_number VARCHAR(24) NOT NULL UNIQUE,
  member_id INT UNSIGNED NOT NULL,
  product_id SMALLINT UNSIGNED NOT NULL,
  branch_id SMALLINT UNSIGNED NOT NULL,
  requested_amount DECIMAL(14,2) NOT NULL,
  requested_term_months SMALLINT UNSIGNED NOT NULL,
  proposal_date DATE NOT NULL,
  loan_purpose VARCHAR(120) NOT NULL,
  economic_sector VARCHAR(60) NOT NULL,
  monthly_household_income DECIMAL(14,2) NOT NULL,
  monthly_household_expense DECIMAL(14,2) NOT NULL,
  monthly_business_revenue DECIMAL(14,2) NOT NULL,
  monthly_business_expense DECIMAL(14,2) NOT NULL,
  existing_liabilities DECIMAL(14,2) NOT NULL,
  appraisal_score DECIMAL(5,2) NOT NULL,
  risk_grade ENUM('A','B','C','D') NOT NULL,
  proposed_by INT UNSIGNED NOT NULL,
  status ENUM('DRAFT','SUBMITTED','APPROVED','REJECTED','CANCELLED') NOT NULL,
  submitted_at_utc DATETIME(6) NULL,
  decided_at_utc DATETIME(6) NULL,
  decision_reason VARCHAR(160) NULL,
  CONSTRAINT fk_proposal_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_proposal_product FOREIGN KEY (product_id) REFERENCES loan_products(product_id),
  CONSTRAINT fk_proposal_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_proposal_staff FOREIGN KEY (proposed_by) REFERENCES staff(staff_id),
  INDEX ix_proposal_reporting (branch_id, product_id, status, proposal_date),
  INDEX ix_proposal_officer (proposed_by, status)
) ENGINE=InnoDB COMMENT='Loan request, cash-flow appraisal, risk and decision pipeline';

CREATE TABLE proposal_guarantors (
  guarantor_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  proposal_id INT UNSIGNED NOT NULL,
  guarantor_name VARCHAR(100) NOT NULL,
  relationship_to_member VARCHAR(40) NOT NULL,
  mobile_number VARCHAR(20) NOT NULL COMMENT 'Synthetic contact number',
  monthly_income DECIMAL(14,2) NOT NULL,
  identity_hash CHAR(64) NOT NULL,
  CONSTRAINT fk_guarantor_proposal FOREIGN KEY (proposal_id) REFERENCES loan_proposals(proposal_id),
  INDEX ix_guarantor_proposal (proposal_id)
) ENGINE=InnoDB COMMENT='Synthetic guarantor data; only a hash represents identity';

CREATE TABLE proposal_approvals (
  approval_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  proposal_id INT UNSIGNED NOT NULL,
  approval_step TINYINT UNSIGNED NOT NULL,
  approver_id INT UNSIGNED NOT NULL,
  decision ENUM('RECOMMENDED','APPROVED','REJECTED','RETURNED') NOT NULL,
  decision_at_utc DATETIME(6) NOT NULL,
  comments VARCHAR(200) NULL,
  CONSTRAINT fk_approval_proposal FOREIGN KEY (proposal_id) REFERENCES loan_proposals(proposal_id),
  CONSTRAINT fk_approval_staff FOREIGN KEY (approver_id) REFERENCES staff(staff_id),
  UNIQUE KEY uq_proposal_step (proposal_id, approval_step)
) ENGINE=InnoDB COMMENT='Multi-step recommendation and approval history';

CREATE TABLE loan_accounts (
  loan_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  loan_account_number VARCHAR(24) NOT NULL UNIQUE,
  proposal_id INT UNSIGNED NOT NULL UNIQUE,
  member_id INT UNSIGNED NOT NULL,
  product_id SMALLINT UNSIGNED NOT NULL,
  branch_id SMALLINT UNSIGNED NOT NULL,
  responsible_officer_id INT UNSIGNED NOT NULL,
  approved_amount DECIMAL(14,2) NOT NULL,
  disbursed_amount DECIMAL(14,2) NOT NULL,
  total_service_charge DECIMAL(14,2) NOT NULL,
  installment_amount DECIMAL(14,2) NOT NULL,
  repayment_frequency ENUM('WEEKLY','MONTHLY') NOT NULL,
  term_installments SMALLINT UNSIGNED NOT NULL,
  approval_date DATE NOT NULL,
  disbursement_date DATE NOT NULL,
  first_due_date DATE NOT NULL,
  maturity_date DATE NOT NULL,
  principal_outstanding DECIMAL(14,2) NOT NULL,
  service_charge_outstanding DECIMAL(14,2) NOT NULL,
  overdue_amount DECIMAL(14,2) NOT NULL,
  days_past_due INT UNSIGNED NOT NULL,
  par_bucket ENUM('CURRENT','PAR_1','PAR_30','PAR_60','PAR_90') NOT NULL,
  classification ENUM('STANDARD','WATCH','SUBSTANDARD','DOUBTFUL','LOSS') NOT NULL,
  rescheduled_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
  write_off_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  status ENUM('ACTIVE','CLOSED','DELINQUENT','RESCHEDULED','WRITTEN_OFF') NOT NULL,
  closure_date DATE NULL,
  created_at_utc DATETIME(6) NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_loan_proposal FOREIGN KEY (proposal_id) REFERENCES loan_proposals(proposal_id),
  CONSTRAINT fk_loan_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_loan_product FOREIGN KEY (product_id) REFERENCES loan_products(product_id),
  CONSTRAINT fk_loan_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_loan_officer FOREIGN KEY (responsible_officer_id) REFERENCES staff(staff_id),
  INDEX ix_loan_portfolio (branch_id, product_id, status, par_bucket),
  INDEX ix_loan_member (member_id, disbursement_date)
) ENGINE=InnoDB COMMENT='Current loan balance, arrears, PAR and classification state';

CREATE TABLE loan_disbursements (
  disbursement_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  loan_id INT UNSIGNED NOT NULL,
  business_date DATE NOT NULL,
  disbursement_amount DECIMAL(14,2) NOT NULL,
  channel ENUM('CASH','BANK','MOBILE_FINANCIAL_SERVICE') NOT NULL,
  external_reference VARCHAR(50) NULL,
  status ENUM('POSTED','REVERSED') NOT NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  updated_by INT UNSIGNED NOT NULL,
  created_at_utc DATETIME(6) NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_disbursement_loan FOREIGN KEY (loan_id) REFERENCES loan_accounts(loan_id),
  CONSTRAINT fk_disbursement_staff FOREIGN KEY (created_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_disbursement_updated_staff FOREIGN KEY (updated_by) REFERENCES staff(staff_id),
  INDEX ix_disbursement_date (business_date, loan_id)
) ENGINE=InnoDB COMMENT='Auditable loan disbursement transactions';

CREATE TABLE repayment_schedules (
  schedule_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  loan_id INT UNSIGNED NOT NULL,
  installment_number SMALLINT UNSIGNED NOT NULL,
  due_date DATE NOT NULL,
  principal_due DECIMAL(14,2) NOT NULL,
  service_charge_due DECIMAL(14,2) NOT NULL,
  principal_paid DECIMAL(14,2) NOT NULL DEFAULT 0,
  service_charge_paid DECIMAL(14,2) NOT NULL DEFAULT 0,
  penalty_paid DECIMAL(14,2) NOT NULL DEFAULT 0,
  paid_date DATE NULL,
  days_past_due INT UNSIGNED NOT NULL DEFAULT 0,
  status ENUM('FUTURE','DUE','PARTIAL','PAID','OVERDUE') NOT NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  updated_by INT UNSIGNED NOT NULL,
  created_at_utc DATETIME(6) NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_schedule_loan FOREIGN KEY (loan_id) REFERENCES loan_accounts(loan_id),
  CONSTRAINT fk_schedule_created_staff FOREIGN KEY (created_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_schedule_updated_staff FOREIGN KEY (updated_by) REFERENCES staff(staff_id),
  UNIQUE KEY uq_loan_installment (loan_id, installment_number),
  INDEX ix_schedule_due (due_date, status),
  INDEX ix_schedule_loan_status (loan_id, status)
) ENGINE=InnoDB COMMENT='Installment-level principal, charge, paid and overdue amounts';

CREATE TABLE collection_receipts (
  receipt_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  receipt_number VARCHAR(30) NOT NULL UNIQUE,
  member_id INT UNSIGNED NOT NULL,
  branch_id SMALLINT UNSIGNED NOT NULL,
  collection_officer_id INT UNSIGNED NOT NULL,
  business_date DATE NOT NULL,
  collected_at_utc DATETIME(6) NOT NULL,
  channel ENUM('VO_MEETING','BRANCH_CASH','BANK','MOBILE_FINANCIAL_SERVICE') NOT NULL,
  total_amount DECIMAL(14,2) NOT NULL,
  external_reference VARCHAR(50) NULL,
  status ENUM('POSTED','REVERSED') NOT NULL,
  reversal_of_receipt_id BIGINT UNSIGNED NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  updated_by INT UNSIGNED NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_receipt_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_receipt_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_receipt_officer FOREIGN KEY (collection_officer_id) REFERENCES staff(staff_id),
  CONSTRAINT fk_receipt_updated_staff FOREIGN KEY (updated_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_receipt_reversal FOREIGN KEY (reversal_of_receipt_id) REFERENCES collection_receipts(receipt_id),
  INDEX ix_receipt_reporting (business_date, branch_id, status),
  INDEX ix_receipt_member (member_id, business_date)
) ENGINE=InnoDB COMMENT='Collection receipt header with channel and reversal audit trail';

CREATE TABLE collection_allocations (
  allocation_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  receipt_id BIGINT UNSIGNED NOT NULL,
  loan_id INT UNSIGNED NULL,
  schedule_id BIGINT UNSIGNED NULL,
  principal_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  service_charge_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  penalty_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  savings_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  other_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  business_date DATE NOT NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  updated_by INT UNSIGNED NOT NULL,
  created_at_utc DATETIME(6) NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_allocation_receipt FOREIGN KEY (receipt_id) REFERENCES collection_receipts(receipt_id),
  CONSTRAINT fk_allocation_loan FOREIGN KEY (loan_id) REFERENCES loan_accounts(loan_id),
  CONSTRAINT fk_allocation_schedule FOREIGN KEY (schedule_id) REFERENCES repayment_schedules(schedule_id),
  CONSTRAINT fk_allocation_created_staff FOREIGN KEY (created_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_allocation_updated_staff FOREIGN KEY (updated_by) REFERENCES staff(staff_id),
  INDEX ix_allocation_loan (loan_id, schedule_id)
) ENGINE=InnoDB COMMENT='Receipt reconciliation across loan, penalty, savings and other components';

CREATE TABLE savings_accounts (
  savings_account_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  account_number VARCHAR(24) NOT NULL UNIQUE,
  member_id INT UNSIGNED NOT NULL,
  branch_id SMALLINT UNSIGNED NOT NULL,
  savings_product ENUM('GENERAL','DPS_DEMO') NOT NULL,
  opening_date DATE NOT NULL,
  closing_date DATE NULL,
  current_balance DECIMAL(14,2) NOT NULL,
  status ENUM('ACTIVE','DORMANT','CLOSED') NOT NULL,
  CONSTRAINT fk_savings_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_savings_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  INDEX ix_savings_member (member_id, status)
) ENGINE=InnoDB COMMENT='Member savings account master and current reconciled balance';

CREATE TABLE savings_transactions (
  savings_transaction_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  savings_account_id INT UNSIGNED NOT NULL,
  receipt_id BIGINT UNSIGNED NULL,
  business_date DATE NOT NULL,
  transaction_type ENUM('DEPOSIT','WITHDRAWAL','INTEREST','REVERSAL') NOT NULL,
  amount DECIMAL(14,2) NOT NULL COMMENT 'Signed amount: credits positive, withdrawals/reversals negative',
  running_balance DECIMAL(14,2) NOT NULL,
  status ENUM('POSTED','REVERSED') NOT NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  updated_by INT UNSIGNED NOT NULL,
  created_at_utc DATETIME(6) NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_savings_tx_account FOREIGN KEY (savings_account_id) REFERENCES savings_accounts(savings_account_id),
  CONSTRAINT fk_savings_tx_receipt FOREIGN KEY (receipt_id) REFERENCES collection_receipts(receipt_id),
  CONSTRAINT fk_savings_tx_staff FOREIGN KEY (created_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_savings_tx_updated_staff FOREIGN KEY (updated_by) REFERENCES staff(staff_id),
  INDEX ix_savings_tx_date (business_date, savings_account_id)
) ENGINE=InnoDB COMMENT='Posted savings ledger with signed amounts and running balances';

CREATE TABLE loan_adjustments (
  adjustment_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  loan_id INT UNSIGNED NOT NULL,
  business_date DATE NOT NULL,
  adjustment_type ENUM('RESCHEDULE','PENALTY_WAIVER','CHARGE_WAIVER','WRITE_OFF','RECOVERY') NOT NULL,
  principal_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  service_charge_amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  reason VARCHAR(160) NOT NULL,
  approved_by INT UNSIGNED NOT NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  updated_by INT UNSIGNED NOT NULL,
  created_at_utc DATETIME(6) NOT NULL,
  updated_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_adjustment_loan FOREIGN KEY (loan_id) REFERENCES loan_accounts(loan_id),
  CONSTRAINT fk_adjustment_approver FOREIGN KEY (approved_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_adjustment_created_staff FOREIGN KEY (created_by) REFERENCES staff(staff_id),
  CONSTRAINT fk_adjustment_updated_staff FOREIGN KEY (updated_by) REFERENCES staff(staff_id),
  INDEX ix_adjustment_date (business_date, adjustment_type)
) ENGINE=InnoDB COMMENT='Approved reschedule, waiver, write-off and recovery events';

CREATE TABLE loan_status_history (
  loan_status_history_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  loan_id INT UNSIGNED NOT NULL,
  previous_status VARCHAR(20) NULL,
  new_status ENUM('ACTIVE','CLOSED','DELINQUENT','RESCHEDULED','WRITTEN_OFF') NOT NULL,
  effective_date DATE NOT NULL,
  reason VARCHAR(160) NULL,
  source VARCHAR(30) NOT NULL,
  created_by INT UNSIGNED NOT NULL,
  created_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_loan_history FOREIGN KEY (loan_id) REFERENCES loan_accounts(loan_id),
  CONSTRAINT fk_loan_history_staff FOREIGN KEY (created_by) REFERENCES staff(staff_id),
  INDEX ix_loan_history (loan_id, effective_date)
) ENGINE=InnoDB COMMENT='Auditable loan status lifecycle';

CREATE TABLE loan_monthly_snapshots (
  snapshot_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  snapshot_month DATE NOT NULL COMMENT 'Calendar month end reporting date',
  loan_id INT UNSIGNED NOT NULL,
  member_id INT UNSIGNED NOT NULL,
  branch_id SMALLINT UNSIGNED NOT NULL,
  product_id SMALLINT UNSIGNED NOT NULL,
  responsible_officer_id INT UNSIGNED NOT NULL,
  principal_outstanding DECIMAL(14,2) NOT NULL,
  service_charge_outstanding DECIMAL(14,2) NOT NULL,
  overdue_amount DECIMAL(14,2) NOT NULL,
  days_past_due INT UNSIGNED NOT NULL,
  par_bucket ENUM('CURRENT','PAR_1','PAR_30','PAR_60','PAR_90') NOT NULL,
  classification ENUM('STANDARD','WATCH','SUBSTANDARD','DOUBTFUL','LOSS') NOT NULL,
  loan_status ENUM('ACTIVE','CLOSED','DELINQUENT','RESCHEDULED','WRITTEN_OFF') NOT NULL,
  created_at_utc DATETIME(6) NOT NULL,
  CONSTRAINT fk_snapshot_loan FOREIGN KEY (loan_id) REFERENCES loan_accounts(loan_id),
  CONSTRAINT fk_snapshot_member FOREIGN KEY (member_id) REFERENCES members(member_id),
  CONSTRAINT fk_snapshot_branch FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
  CONSTRAINT fk_snapshot_product FOREIGN KEY (product_id) REFERENCES loan_products(product_id),
  CONSTRAINT fk_snapshot_officer FOREIGN KEY (responsible_officer_id) REFERENCES staff(staff_id),
  UNIQUE KEY uq_snapshot_loan_month (snapshot_month, loan_id),
  INDEX ix_snapshot_reporting (snapshot_month, branch_id, product_id, par_bucket)
) ENGINE=InnoDB COMMENT='Month-end point-in-time portfolio and PAR facts';
