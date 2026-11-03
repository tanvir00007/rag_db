CREATE OR REPLACE VIEW vw_member_360 AS
SELECT m.member_id, m.member_number, m.full_name, m.gender, m.member_type, m.status AS member_status,
       m.enrollment_date, b.branch_code, b.branch_name, b.division_name, b.district_name, b.upazila_name,
       vo.vo_code, vo.vo_name, m.primary_livelihood, m.monthly_household_income, m.monthly_household_expense,
       m.poverty_score, m.vulnerable_household, m.disability_indicator,
       COALESCE(la.lifetime_loan_count, 0) AS lifetime_loan_count,
       COALESCE(la.open_loan_count, 0) AS open_loan_count,
       COALESCE(la.principal_outstanding, 0) AS principal_outstanding,
       COALESCE(la.maximum_days_past_due, 0) AS maximum_days_past_due,
       COALESCE(sa.savings_balance, 0) AS savings_balance
FROM members m
JOIN branches b ON b.branch_id=m.branch_id
LEFT JOIN village_organizations vo ON vo.vo_id=m.vo_id
LEFT JOIN (
  SELECT member_id, COUNT(*) AS lifetime_loan_count,
         SUM(status IN ('ACTIVE','DELINQUENT','RESCHEDULED')) AS open_loan_count,
         SUM(principal_outstanding) AS principal_outstanding,
         MAX(days_past_due) AS maximum_days_past_due
  FROM loan_accounts GROUP BY member_id
) la ON la.member_id=m.member_id
LEFT JOIN (
  SELECT member_id, SUM(current_balance) AS savings_balance
  FROM savings_accounts WHERE status <> 'CLOSED' GROUP BY member_id
) sa ON sa.member_id=m.member_id;

CREATE OR REPLACE VIEW vw_member_profile_updates AS
SELECT pur.update_request_id, pur.request_number, m.member_number, m.full_name, b.branch_code, b.branch_name,
       pur.request_date, pur.request_source, pur.reason, pur.status, s.employee_number AS reviewer_employee_number,
       TIMESTAMPDIFF(HOUR, pur.submitted_at_utc, COALESCE(pur.decided_at_utc, UTC_TIMESTAMP())) AS processing_hours,
       GROUP_CONCAT(CONCAT(pud.field_name, ': ', COALESCE(pud.previous_value,''), ' -> ', COALESCE(pud.new_value,''))
                    ORDER BY pud.update_detail_id SEPARATOR '; ') AS field_changes
FROM profile_update_requests pur
JOIN members m ON m.member_id=pur.member_id
JOIN branches b ON b.branch_id=pur.branch_id
LEFT JOIN staff s ON s.staff_id=pur.reviewed_by
LEFT JOIN profile_update_details pud ON pud.update_request_id=pur.update_request_id
GROUP BY pur.update_request_id, pur.request_number, m.member_number, m.full_name, b.branch_code, b.branch_name,
         pur.request_date, pur.request_source, pur.reason, pur.status, s.employee_number,
         pur.submitted_at_utc, pur.decided_at_utc;

CREATE OR REPLACE VIEW vw_proposal_pipeline AS
SELECT lp.proposal_id, lp.proposal_number, lp.proposal_date, lp.status, lp.requested_amount,
       lp.requested_term_months, lp.loan_purpose, lp.economic_sector, lp.appraisal_score, lp.risk_grade,
       TIMESTAMPDIFF(HOUR, lp.submitted_at_utc, lp.decided_at_utc) AS decision_turnaround_hours,
       m.member_number, m.full_name, m.gender, b.branch_code, b.branch_name,
       p.product_code, p.product_name, s.employee_number AS officer_employee_number, s.full_name AS officer_name
FROM loan_proposals lp
JOIN members m ON m.member_id=lp.member_id
JOIN branches b ON b.branch_id=lp.branch_id
JOIN loan_products p ON p.product_id=lp.product_id
JOIN staff s ON s.staff_id=lp.proposed_by;

CREATE OR REPLACE VIEW vw_loan_portfolio AS
SELECT la.loan_id, la.loan_account_number, m.member_number, m.full_name, m.gender,
       b.branch_code, b.branch_name, b.division_name, b.district_name,
       p.product_code, p.product_name, p.lending_mode, s.employee_number AS officer_employee_number,
       la.approved_amount, la.disbursed_amount, la.total_service_charge, la.installment_amount,
       la.repayment_frequency, la.term_installments, la.disbursement_date, la.maturity_date,
       la.principal_outstanding, la.service_charge_outstanding,
       la.principal_outstanding + la.service_charge_outstanding AS total_outstanding,
       la.overdue_amount, la.days_past_due, la.par_bucket, la.classification,
       la.rescheduled_count, la.write_off_amount, la.status, la.closure_date
FROM loan_accounts la
JOIN members m ON m.member_id=la.member_id
JOIN branches b ON b.branch_id=la.branch_id
JOIN loan_products p ON p.product_id=la.product_id
JOIN staff s ON s.staff_id=la.responsible_officer_id;

CREATE OR REPLACE VIEW vw_collection_due_vs_actual AS
SELECT rs.due_date AS reporting_date, la.branch_id, b.branch_code, b.branch_name, la.product_id,
       p.product_code, p.product_name, la.responsible_officer_id, s.employee_number AS officer_employee_number,
       SUM(rs.principal_due + rs.service_charge_due) AS amount_due,
       SUM(rs.principal_paid + rs.service_charge_paid + rs.penalty_paid) AS amount_collected,
       SUM(rs.principal_due + rs.service_charge_due - rs.principal_paid - rs.service_charge_paid) AS amount_unpaid,
       ROUND(100 * SUM(rs.principal_paid + rs.service_charge_paid) /
             NULLIF(SUM(rs.principal_due + rs.service_charge_due), 0), 2) AS collection_efficiency_percent,
       SUM(rs.status='PAID') AS paid_installments, SUM(rs.status='OVERDUE') AS overdue_installments
FROM repayment_schedules rs
JOIN loan_accounts la ON la.loan_id=rs.loan_id
JOIN branches b ON b.branch_id=la.branch_id
JOIN loan_products p ON p.product_id=la.product_id
JOIN staff s ON s.staff_id=la.responsible_officer_id
GROUP BY rs.due_date, la.branch_id, b.branch_code, b.branch_name, la.product_id, p.product_code,
         p.product_name, la.responsible_officer_id, s.employee_number;

CREATE OR REPLACE VIEW vw_collection_transactions AS
SELECT cr.receipt_id, cr.receipt_number, cr.business_date, cr.collected_at_utc, cr.channel, cr.status,
       cr.total_amount, m.member_number, m.full_name, b.branch_code, b.branch_name,
       s.employee_number AS collection_officer_number, la.loan_account_number, rs.installment_number,
       ca.principal_amount, ca.service_charge_amount, ca.penalty_amount, ca.savings_amount, ca.other_amount
FROM collection_receipts cr
JOIN members m ON m.member_id=cr.member_id
JOIN branches b ON b.branch_id=cr.branch_id
JOIN staff s ON s.staff_id=cr.collection_officer_id
JOIN collection_allocations ca ON ca.receipt_id=cr.receipt_id
LEFT JOIN loan_accounts la ON la.loan_id=ca.loan_id
LEFT JOIN repayment_schedules rs ON rs.schedule_id=ca.schedule_id;

CREATE OR REPLACE VIEW vw_branch_monthly_kpis AS
SELECT lms.snapshot_month, b.branch_id, b.branch_code, b.branch_name, b.division_name, b.district_name,
       COUNT(DISTINCT lms.loan_id) AS loan_count, COUNT(DISTINCT lms.member_id) AS borrower_count,
       SUM(lms.principal_outstanding) AS principal_outstanding, SUM(lms.overdue_amount) AS overdue_amount,
       SUM(lms.par_bucket <> 'CURRENT') AS par_1_loan_count,
       SUM(lms.par_bucket IN ('PAR_30','PAR_60','PAR_90')) AS par_30_loan_count,
       SUM(lms.par_bucket IN ('PAR_60','PAR_90')) AS par_60_loan_count,
       SUM(lms.par_bucket = 'PAR_90') AS par_90_loan_count,
       ROUND(100 * SUM(CASE WHEN lms.par_bucket <> 'CURRENT' THEN lms.principal_outstanding ELSE 0 END) /
             NULLIF(SUM(lms.principal_outstanding),0), 2) AS par_1_percent,
       ROUND(100 * SUM(CASE WHEN lms.par_bucket IN ('PAR_30','PAR_60','PAR_90') THEN lms.principal_outstanding ELSE 0 END) /
             NULLIF(SUM(lms.principal_outstanding),0), 2) AS par_30_percent
FROM loan_monthly_snapshots lms JOIN branches b ON b.branch_id=lms.branch_id
GROUP BY lms.snapshot_month, b.branch_id, b.branch_code, b.branch_name, b.division_name, b.district_name;

CREATE OR REPLACE VIEW vw_product_monthly_kpis AS
SELECT lms.snapshot_month, p.product_id, p.product_code, p.product_name, p.lending_mode,
       COUNT(DISTINCT lms.loan_id) AS loan_count, COUNT(DISTINCT lms.member_id) AS borrower_count,
       SUM(lms.principal_outstanding) AS principal_outstanding, SUM(lms.overdue_amount) AS overdue_amount,
       ROUND(100 * SUM(CASE WHEN lms.par_bucket <> 'CURRENT' THEN lms.principal_outstanding ELSE 0 END) /
             NULLIF(SUM(lms.principal_outstanding),0), 2) AS par_1_percent,
       ROUND(100 * SUM(CASE WHEN lms.par_bucket IN ('PAR_30','PAR_60','PAR_90') THEN lms.principal_outstanding ELSE 0 END) /
             NULLIF(SUM(lms.principal_outstanding),0), 2) AS par_30_percent
FROM loan_monthly_snapshots lms JOIN loan_products p ON p.product_id=lms.product_id
GROUP BY lms.snapshot_month, p.product_id, p.product_code, p.product_name, p.lending_mode;
