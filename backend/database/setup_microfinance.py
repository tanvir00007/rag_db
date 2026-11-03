from __future__ import annotations

import argparse
import calendar
import hashlib
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, Sequence

import pymysql

from app.core.config_store import load_mysql_config


DATABASE_NAME = "brac_microfinance_demo"
RANDOM_SEED = 20260805
AS_OF_DATE = date(2026, 8, 5)
NOW_UTC = datetime(2026, 8, 5, 12, 0, 0)
MONEY = Decimal("0.01")
HERE = Path(__file__).resolve().parent


def q(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def month_end(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def chunks(rows: Sequence[tuple], size: int = 5000) -> Iterable[Sequence[tuple]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def insert_many(cursor, sql: str, rows: Sequence[tuple], size: int = 5000) -> None:
    for batch in chunks(rows, size):
        cursor.executemany(sql, batch)


def execute_sql_file(cursor, path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    for statement in content.split(";\n"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def server_connection(database: str | None = None):
    config = load_mysql_config()
    if not config:
        raise RuntimeError("Save a MySQL connection in the app before running the setup command.")
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.username,
        password=config.password,
        database=database,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.Cursor,
        ssl={} if config.ssl else None,
    )


def prepare_database(reset: bool) -> None:
    connection = server_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW DATABASES LIKE %s", (DATABASE_NAME,))
            exists = cursor.fetchone() is not None
            if exists:
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s",
                    (DATABASE_NAME,),
                )
                populated = int(cursor.fetchone()[0]) > 0
                if populated and not reset:
                    raise RuntimeError(
                        f"{DATABASE_NAME} already contains objects. Re-run with --reset to replace only this demo database."
                    )
                if reset:
                    cursor.execute(f"DROP DATABASE `{DATABASE_NAME}`")
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


LOCATIONS = [
    ("Dhaka", "Dhaka", "Savar"), ("Dhaka", "Gazipur", "Kaliakair"),
    ("Chattogram", "Cumilla", "Daudkandi"), ("Chattogram", "Noakhali", "Begumganj"),
    ("Rajshahi", "Rajshahi", "Paba"), ("Rajshahi", "Bogra", "Sherpur"),
    ("Khulna", "Jashore", "Jhikargacha"), ("Khulna", "Kushtia", "Kumarkhali"),
    ("Rangpur", "Rangpur", "Mithapukur"), ("Rangpur", "Dinajpur", "Birganj"),
    ("Sylhet", "Sylhet", "Golapganj"), ("Sylhet", "Moulvibazar", "Sreemangal"),
    ("Barishal", "Barishal", "Bakerganj"), ("Barishal", "Patuakhali", "Dumki"),
    ("Mymensingh", "Mymensingh", "Trishal"), ("Mymensingh", "Jamalpur", "Islampur"),
]
FEMALE_NAMES = ["Ayesha Akter", "Shamima Begum", "Rokeya Khatun", "Nasima Sultana", "Taslima Begum", "Jannat Ara", "Mst Rina", "Farzana Yasmin", "Salma Khatun", "Nusrat Jahan"]
MALE_NAMES = ["Abdul Karim", "Md Rahim", "Jamal Uddin", "Sohel Rana", "Monir Hossain", "Rafiqul Islam", "Anwar Hossain", "Babul Mia", "Hasan Ali", "Shahidul Islam"]
LIVELIHOODS = ["Small retail", "Dairy farming", "Poultry", "Tailoring", "Crop farming", "Food processing", "Transport", "Handicrafts", "Fisheries", "Wage employment"]
SECTORS = ["Trade", "Livestock", "Agriculture", "Services", "Manufacturing", "Transport", "Migration"]


def seed_reference_data(cursor, rng: random.Random) -> dict[str, object]:
    regions = [(i + 1, f"R{i+1:02d}", name, name, "ACTIVE") for i, name in enumerate(["Central", "East", "North", "South", "West"])]
    cursor.executemany("INSERT INTO regions VALUES (%s,%s,%s,%s,%s)", regions)

    areas = []
    for i in range(10):
        division, district, _ = LOCATIONS[i]
        areas.append((i + 1, i // 2 + 1, f"A{i+1:02d}", f"{district} Area {i%2+1}", district, "ACTIVE"))
    cursor.executemany("INSERT INTO areas VALUES (%s,%s,%s,%s,%s,%s)", areas)

    branches = []
    for i in range(50):
        division, district, upazila = LOCATIONS[i % len(LOCATIONS)]
        branches.append((i + 1, i // 5 + 1, f"B{i+1:03d}", f"{upazila} Demo Branch {i//len(LOCATIONS)+1}", division, district, upazila, date(2012 + i % 11, 1 + i % 12, 1), "ACTIVE"))
    cursor.executemany("INSERT INTO branches VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", branches)

    staff_rows = []
    staff_by_branch: dict[int, list[int]] = defaultdict(list)
    role_order = ["BRANCH_MANAGER", "CREDIT_OFFICER", "CREDIT_OFFICER", "COLLECTION_OFFICER", "KYC_OFFICER", "CASHIER"]
    for branch_id in range(1, 51):
        manager_id = (branch_id - 1) * 6 + 1
        for position, role in enumerate(role_order):
            staff_id = manager_id + position
            gender_names = FEMALE_NAMES if (staff_id + position) % 3 else MALE_NAMES
            staff_rows.append((staff_id, f"EMP{staff_id:05d}", branch_id, gender_names[staff_id % len(gender_names)], role, None if position == 0 else manager_id, date(2017 + staff_id % 7, 1 + staff_id % 12, 1 + staff_id % 25), None, "ACTIVE"))
            staff_by_branch[branch_id].append(staff_id)
    cursor.executemany("INSERT INTO staff VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", staff_rows)

    vo_rows = []
    vos_by_branch: dict[int, list[int]] = defaultdict(list)
    for branch_id in range(1, 51):
        for local in range(5):
            vo_id = (branch_id - 1) * 5 + local + 1
            officer = (branch_id - 1) * 6 + 2 + local % 2
            village = f"{LOCATIONS[(branch_id + local) % len(LOCATIONS)][2]} Village {local+1}"
            vo_rows.append((vo_id, branch_id, f"VO{vo_id:04d}", f"Shapla VO {vo_id:04d}", village, "WEEKLY" if local < 4 else "MONTHLY", local % 6 + 1, officer, date(2018 + local, 1 + local * 2, 1), "ACTIVE"))
            vos_by_branch[branch_id].append(vo_id)
    cursor.executemany("INSERT INTO village_organizations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", vo_rows)

    products = [
        (1, "DABI-DEMO", "Dabi Group Loan (Demo)", "GROUP", "GROUP", "General livelihood", q(10000), q(100000), 12, "WEEKLY", 7, "FLAT_DEMO", Decimal("0.20"), Decimal("0.05"), "ACTIVE"),
        (2, "PROGOTI-DEMO", "Progoti Enterprise Loan (Demo)", "INDIVIDUAL", "INDIVIDUAL", "Microenterprise", q(50000), q(500000), 18, "MONTHLY", 15, "DECLINING_DEMO", Decimal("0.18"), Decimal("0.02"), "ACTIVE"),
        (3, "AGRI-DEMO", "Agriculture Loan (Demo)", "GROUP", "BOTH", "Agriculture", q(20000), q(200000), 12, "MONTHLY", 30, "FLAT_DEMO", Decimal("0.16"), Decimal("0.03"), "ACTIVE"),
        (4, "MIGRATION-DEMO", "Migration Loan (Demo)", "INDIVIDUAL", "BOTH", "Migration", q(50000), q(300000), 18, "MONTHLY", 30, "DECLINING_DEMO", Decimal("0.17"), Decimal("0.02"), "ACTIVE"),
    ]
    cursor.executemany("INSERT INTO loan_products VALUES (" + ",".join(["%s"] * 15) + ")", products)
    return {"staff_by_branch": staff_by_branch, "vos_by_branch": vos_by_branch}


def seed_members(cursor, rng: random.Random, refs: dict[str, object]) -> list[dict]:
    staff_by_branch = refs["staff_by_branch"]
    vos_by_branch = refs["vos_by_branch"]
    enrollment_rows, member_rows, vo_membership_rows, kyc_rows, history_rows = [], [], [], [], []
    members: list[dict] = []
    for member_id in range(1, 5001):
        branch_id = (member_id * 17) % 50 + 1
        member_type = "GROUP" if member_id % 4 else "INDIVIDUAL"
        vo_id = rng.choice(vos_by_branch[branch_id]) if member_type == "GROUP" else None
        app_date = random_date(rng, date(2024, 1, 1), date(2026, 6, 15))
        enroll_date = app_date + timedelta(days=rng.randint(1, 7))
        gender = "FEMALE" if (member_type == "GROUP" or member_id % 3) else "MALE"
        name_pool = FEMALE_NAMES if gender == "FEMALE" else MALE_NAMES
        full_name = f"{name_pool[member_id % len(name_pool)]} {member_id:04d}"
        raw_identity = f"SYNTHETIC-NID-{member_id:010d}"
        income = q(rng.randrange(12000, 65001, 500))
        expense = q(float(income) * rng.uniform(0.52, 0.88))
        status = "EXITED" if member_id % 97 == 0 else ("SUSPENDED" if member_id % 149 == 0 else "ACTIVE")
        exit_date = min(enroll_date + timedelta(days=400 + member_id % 300), AS_OF_DATE) if status == "EXITED" else None
        submitted = datetime.combine(app_date, time(4, 0))
        decided = datetime.combine(enroll_date, time(8, 0))
        enrollment_rows.append((member_id, f"ENR{member_id:08d}", app_date, rng.choice(["BRANCH", "FIELD_APP", "REFERRAL"]), branch_id, vo_id, member_type, "VERIFIED", "APPROVED", staff_by_branch[branch_id][4], staff_by_branch[branch_id][0], submitted, decided, None))
        member_rows.append((member_id, f"MBR{member_id:08d}", member_id, branch_id, vo_id, member_type, full_name, gender, date(1968 + member_id % 35, member_id % 12 + 1, member_id % 27 + 1), f"01{3 + member_id % 7}{member_id:08d}"[-11:], raw_identity[-4:], hashlib.sha256(raw_identity.encode()).hexdigest(), rng.choice(["SINGLE", "MARRIED", "WIDOWED"]), rng.choice(["NONE", "PRIMARY", "SECONDARY", "HIGHER"]), rng.choice(LIVELIHOODS), 2 + member_id % 7, 1 + member_id % 3, income, expense, q(rng.uniform(18, 86)), member_id % 11 == 0, member_id % 79 == 0, enroll_date, status, exit_date, datetime.combine(enroll_date, time(8)), NOW_UTC))
        if vo_id:
            vo_membership_rows.append((member_id, member_id, vo_id, enroll_date, exit_date, "EXITED" if exit_date else "ACTIVE"))
        kyc_rows.append((member_id, member_id, "NID_HASH", "VERIFIED", enroll_date, staff_by_branch[branch_id][4], "HIGH" if member_id % 101 == 0 else ("MEDIUM" if member_id % 9 == 0 else "LOW"), "GRANTED", app_date, add_months(enroll_date, 24), datetime.combine(enroll_date, time(8))))
        history_rows.append((member_id, member_id, None, "ACTIVE", enroll_date, "Enrollment approved", "SEED", staff_by_branch[branch_id][0], datetime.combine(enroll_date, time(8))))
        if status != "ACTIVE":
            history_rows.append((5000 + member_id, member_id, "ACTIVE", status, exit_date or AS_OF_DATE - timedelta(days=30), "Synthetic lifecycle event", "SEED", staff_by_branch[branch_id][0], NOW_UTC))
        members.append({"id": member_id, "branch": branch_id, "vo": vo_id, "type": member_type, "name": full_name, "gender": gender, "enroll": enroll_date, "income": income, "expense": expense})

    # Add rejected applications so enrollment reporting has a real rejection cohort.
    for offset in range(1, 251):
        enrollment_id = 5000 + offset
        branch_id = offset % 50 + 1
        app_date = random_date(rng, date(2024, 1, 1), date(2026, 7, 31))
        enrollment_rows.append((enrollment_id, f"ENR{enrollment_id:08d}", app_date, "FIELD_APP", branch_id, None, "INDIVIDUAL", "FAILED", "REJECTED", staff_by_branch[branch_id][4], staff_by_branch[branch_id][0], datetime.combine(app_date, time(4)), datetime.combine(app_date + timedelta(days=2), time(8)), "Synthetic verification criteria not met"))

    insert_many(cursor, "INSERT INTO member_enrollments VALUES (" + ",".join(["%s"] * 14) + ")", enrollment_rows)
    insert_many(cursor, "INSERT INTO members VALUES (" + ",".join(["%s"] * 27) + ")", member_rows)
    insert_many(cursor, "INSERT INTO vo_memberships VALUES (%s,%s,%s,%s,%s,%s)", vo_membership_rows)
    insert_many(cursor, "INSERT INTO kyc_verifications VALUES (" + ",".join(["%s"] * 11) + ")", kyc_rows)
    insert_many(cursor, "INSERT INTO member_status_history VALUES (" + ",".join(["%s"] * 9) + ")", history_rows)
    return members


def seed_profile_updates(cursor, rng: random.Random, members: list[dict], refs: dict[str, object]) -> None:
    rows, details = [], []
    staff_by_branch = refs["staff_by_branch"]
    fields = [("mobile_number", "01300000000", "01700000000"), ("primary_livelihood", "Wage employment", "Small retail"), ("monthly_household_income", "18000.00", "24000.00"), ("marital_status", "SINGLE", "MARRIED"), ("branch_id", "Previous branch", "Current branch")]
    detail_id = 1
    for request_id in range(1, 701):
        member = members[(request_id * 37) % len(members)]
        request_date = min(member["enroll"] + timedelta(days=60 + request_id % 500), AS_OF_DATE)
        status = "PENDING" if request_id % 9 == 0 else ("REJECTED" if request_id % 13 == 0 else "APPROVED")
        submitted = datetime.combine(request_date, time(5))
        decided = None if status == "PENDING" else min(submitted + timedelta(hours=5 + request_id % 72), NOW_UTC)
        rows.append((request_id, f"PUR{request_id:08d}", member["id"], member["branch"], request_date, rng.choice(["BRANCH", "FIELD_APP", "CALL_CENTRE", "MEMBER"]), "Member requested synthetic profile correction", status, None if status == "PENDING" else staff_by_branch[member["branch"]][4], submitted, decided))
        field = fields[request_id % len(fields)]
        details.append((detail_id, request_id, field[0], field[1], field[2])); detail_id += 1
        if request_id % 5 == 0:
            field2 = fields[(request_id + 2) % len(fields)]
            details.append((detail_id, request_id, field2[0], field2[1], field2[2])); detail_id += 1
    insert_many(cursor, "INSERT INTO profile_update_requests VALUES (" + ",".join(["%s"] * 11) + ")", rows)
    insert_many(cursor, "INSERT INTO profile_update_details VALUES (%s,%s,%s,%s,%s)", details)


def seed_proposals(cursor, rng: random.Random, members: list[dict], refs: dict[str, object]) -> list[dict]:
    staff_by_branch = refs["staff_by_branch"]
    rows, approvals, guarantors, approved = [], [], [], []
    approval_id = guarantor_id = 1
    for proposal_id in range(1, 7001):
        member = members[(proposal_id * 29 + proposal_id // 5000) % len(members)]
        if member["type"] == "GROUP":
            product_id = 1 if proposal_id % 5 else 3
        else:
            product_id = 4 if proposal_id % 7 == 0 else 2
        minimum, maximum = {1: (10000, 100000), 2: (50000, 500000), 3: (20000, 200000), 4: (50000, 300000)}[product_id]
        amount = q(rng.randrange(minimum // 5000, maximum // 5000 + 1) * 5000)
        term = {1: 12, 2: 18, 3: 12, 4: 18}[product_id]
        earliest = max(member["enroll"] + timedelta(days=14), date(2024, 1, 15))
        proposal_date = random_date(rng, earliest, date(2026, 6, 20)) if earliest <= date(2026, 6, 20) else earliest
        status = "APPROVED" if proposal_id <= 6000 else ("REJECTED" if proposal_id <= 6800 else "SUBMITTED")
        submitted = datetime.combine(proposal_date, time(5))
        decided = None if status == "SUBMITTED" else submitted + timedelta(hours=12 + proposal_id % 96)
        score = q(48 + (proposal_id * 17) % 50)
        grade = "A" if score >= 85 else ("B" if score >= 70 else ("C" if score >= 58 else "D"))
        officer = staff_by_branch[member["branch"]][1 + proposal_id % 2]
        rows.append((proposal_id, f"LPR{proposal_id:08d}", member["id"], product_id, member["branch"], amount, term, proposal_date, rng.choice(LIVELIHOODS), SECTORS[product_id % len(SECTORS)], member["income"], member["expense"], q(float(member["income"]) * rng.uniform(0.8, 2.5)), q(float(member["expense"]) * rng.uniform(0.4, 1.2)), q(rng.randrange(0, 80001, 5000)), score, grade, officer, status, submitted, decided, None if status == "APPROVED" else ("Synthetic affordability threshold" if status == "REJECTED" else None)))
        decision1 = "RECOMMENDED" if status == "APPROVED" else ("REJECTED" if status == "REJECTED" else "RETURNED")
        if status != "SUBMITTED":
            approvals.append((approval_id, proposal_id, 1, officer, decision1, submitted + timedelta(hours=4), "Synthetic appraisal step")); approval_id += 1
            if status == "APPROVED":
                approvals.append((approval_id, proposal_id, 2, staff_by_branch[member["branch"]][0], "APPROVED", decided, "Approved for demonstration")); approval_id += 1
        if product_id in (2, 4):
            identity = hashlib.sha256(f"SYNTH-GUAR-{proposal_id}".encode()).hexdigest()
            guarantors.append((guarantor_id, proposal_id, f"Synthetic Guarantor {proposal_id}", "Business associate", f"018{proposal_id:08d}"[-11:], q(rng.randrange(20000, 90001, 1000)), identity)); guarantor_id += 1
        if status == "APPROVED":
            approved.append({"proposal": proposal_id, "member": member, "product": product_id, "amount": amount, "term": term, "date": proposal_date, "officer": officer})
    insert_many(cursor, "INSERT INTO loan_proposals VALUES (" + ",".join(["%s"] * 22) + ")", rows)
    insert_many(cursor, "INSERT INTO proposal_approvals VALUES (" + ",".join(["%s"] * 7) + ")", approvals)
    insert_many(cursor, "INSERT INTO proposal_guarantors VALUES (" + ",".join(["%s"] * 7) + ")", guarantors)
    return approved


def delinquency_for(loan_id: int) -> int:
    if loan_id % 97 == 0:
        return 100
    if loan_id % 53 == 0:
        return 65
    if loan_id % 29 == 0:
        return 35
    if loan_id % 11 == 0:
        return 8
    return 0


def par_values(days: int) -> tuple[str, str]:
    if days >= 90: return "PAR_90", "LOSS"
    if days >= 60: return "PAR_60", "DOUBTFUL"
    if days >= 30: return "PAR_30", "SUBSTANDARD"
    if days >= 1: return "PAR_1", "WATCH"
    return "CURRENT", "STANDARD"


def seed_loans_and_transactions(cursor, rng: random.Random, approved: list[dict], refs: dict[str, object]) -> dict[str, int]:
    loans, disbursements, schedules, schedule_meta, loan_histories, adjustments = [], [], [], [], [], []
    schedule_id = 1
    loan_state: dict[int, dict] = {}
    for loan_id, item in enumerate(approved, 1):
        product = item["product"]
        frequency = "WEEKLY" if product == 1 else "MONTHLY"
        installments = 46 if product == 1 else item["term"]
        disb_date = item["date"] + timedelta(days=3 + loan_id % 5)
        first_due = disb_date + (timedelta(days=14) if frequency == "WEEKLY" else timedelta(days=30))
        total_charge = q(float(item["amount"]) * {1: .20, 2: .145, 3: .16, 4: .14}[product])
        principal_parts = [q(item["amount"] / installments) for _ in range(installments)]
        principal_parts[-1] += item["amount"] - sum(principal_parts)
        charge_parts = [q(total_charge / installments) for _ in range(installments)]
        charge_parts[-1] += total_charge - sum(charge_parts)
        missed_days = delinquency_for(loan_id)
        principal_paid_total = Decimal("0"); charge_paid_total = Decimal("0"); overdue = Decimal("0")
        latest_unpaid_due = None
        loan_schedule_ids = []
        for installment in range(1, installments + 1):
            due = first_due + timedelta(days=7 * (installment - 1)) if frequency == "WEEKLY" else add_months(first_due, installment - 1)
            p_due, c_due = principal_parts[installment - 1], charge_parts[installment - 1]
            p_paid = c_paid = Decimal("0"); paid_date = None; status = "FUTURE" if due > AS_OF_DATE else "DUE"
            days_due = max(0, (AS_OF_DATE - due).days)
            if due <= AS_OF_DATE:
                should_miss = missed_days and days_due <= missed_days
                if should_miss:
                    if installment % 3 == 0:
                        p_paid, c_paid = q(p_due * Decimal("0.50")), q(c_due * Decimal("0.50")); status = "PARTIAL"
                    else:
                        status = "OVERDUE"
                    overdue += p_due + c_due - p_paid - c_paid
                    latest_unpaid_due = due if latest_unpaid_due is None else min(latest_unpaid_due, due)
                else:
                    p_paid, c_paid = p_due, c_due
                    paid_date = min(due + timedelta(days=(loan_id + installment) % 6 - 2), AS_OF_DATE)
                    if paid_date < disb_date: paid_date = disb_date
                    status = "PAID"
            principal_paid_total += p_paid; charge_paid_total += c_paid
            dpd = max(0, (AS_OF_DATE - due).days) if status in ("PARTIAL", "OVERDUE") else 0
            schedules.append((schedule_id, loan_id, installment, due, p_due, c_due, p_paid, c_paid, Decimal("0"), paid_date, dpd, status, "SEED", item["officer"], item["officer"], datetime.combine(disb_date, time(5)), NOW_UTC))
            if p_paid + c_paid > 0:
                schedule_meta.append((schedule_id, loan_id, item["member"]["id"], item["member"]["branch"], item["officer"], paid_date or min(due + timedelta(days=2), AS_OF_DATE), p_paid, c_paid, product))
            loan_schedule_ids.append(schedule_id)
            schedule_id += 1
        principal_out = max(Decimal("0"), item["amount"] - principal_paid_total)
        charge_out = max(Decimal("0"), total_charge - charge_paid_total)
        days_past = max(0, (AS_OF_DATE - latest_unpaid_due).days) if latest_unpaid_due else 0
        bucket, classification = par_values(days_past)
        closure = AS_OF_DATE if principal_out == 0 and charge_out == 0 else None
        status = "CLOSED" if closure else ("DELINQUENT" if overdue > 0 else "ACTIVE")
        rescheduled = 1 if loan_id % 101 == 0 and status != "CLOSED" else 0
        if rescheduled: status = "RESCHEDULED"
        maturity = first_due + timedelta(days=7 * (installments - 1)) if frequency == "WEEKLY" else add_months(first_due, installments - 1)
        loans.append((loan_id, f"LON{loan_id:08d}", item["proposal"], item["member"]["id"], product, item["member"]["branch"], item["officer"], item["amount"], item["amount"], total_charge, q((item["amount"] + total_charge) / installments), frequency, installments, item["date"] + timedelta(days=1), disb_date, first_due, maturity, principal_out, charge_out, overdue, days_past, bucket, classification, rescheduled, Decimal("0"), status, closure, datetime.combine(disb_date, time(4)), NOW_UTC))
        disbursements.append((loan_id, loan_id, disb_date, item["amount"], rng.choice(["CASH", "BANK", "MOBILE_FINANCIAL_SERVICE"]), f"SYN-DISB-{loan_id:08d}", "POSTED", "SEED", item["officer"], item["officer"], datetime.combine(disb_date, time(4)), datetime.combine(disb_date, time(4))))
        loan_histories.append((loan_id, loan_id, None, "CLOSED" if closure else "ACTIVE", disb_date, "Synthetic disbursement", "SEED", item["officer"], datetime.combine(disb_date, time(4))))
        if rescheduled:
            manager = refs["staff_by_branch"][item["member"]["branch"]][0]
            adjustments.append((len(adjustments)+1, loan_id, AS_OF_DATE - timedelta(days=loan_id % 60), "RESCHEDULE", Decimal("0"), Decimal("0"), "Synthetic hardship reschedule", manager, "SEED", manager, manager, NOW_UTC, NOW_UTC))
            loan_histories.append((6000 + len(loan_histories), loan_id, "DELINQUENT", "RESCHEDULED", AS_OF_DATE - timedelta(days=loan_id % 60), "Synthetic hardship reschedule", "SEED", item["officer"], NOW_UTC))
        loan_state[loan_id] = {"item": item, "disb": disb_date, "maturity": maturity, "principal": item["amount"], "charge": total_charge, "bucket": bucket, "class": classification, "status": status}

    insert_many(cursor, "INSERT INTO loan_accounts VALUES (" + ",".join(["%s"] * 29) + ")", loans)
    insert_many(cursor, "INSERT INTO loan_disbursements VALUES (" + ",".join(["%s"] * 12) + ")", disbursements)
    insert_many(cursor, "INSERT INTO repayment_schedules VALUES (" + ",".join(["%s"] * 17) + ")", schedules)
    insert_many(cursor, "INSERT INTO loan_status_history VALUES (" + ",".join(["%s"] * 9) + ")", loan_histories)
    if adjustments:
        insert_many(cursor, "INSERT INTO loan_adjustments VALUES (" + ",".join(["%s"] * 13) + ")", adjustments)

    # One general savings account per member. Loan collections may include a small linked savings deposit.
    savings_accounts = [(member_id, f"SAV{member_id:08d}", member_id, (member_id * 17) % 50 + 1, "DPS_DEMO" if member_id % 5 == 0 else "GENERAL", date(2024, 1, 1), None, Decimal("0"), "ACTIVE") for member_id in range(1, 5001)]
    insert_many(cursor, "INSERT INTO savings_accounts VALUES (" + ",".join(["%s"] * 9) + ")", savings_accounts)

    receipts, allocations, savings_txs = [], [], []
    savings_balances: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    receipt_id = allocation_id = savings_tx_id = 1
    original_receipts: list[tuple] = []
    for index, meta in enumerate(schedule_meta, 1):
        sched_id, loan_id, member_id, branch_id, officer, paid_date, p_paid, c_paid, product = meta
        savings = q(100 if product == 1 and index % 3 == 0 else 0)
        total = p_paid + c_paid + savings
        channel = "VO_MEETING" if product == 1 else rng.choice(["BRANCH_CASH", "BANK", "MOBILE_FINANCIAL_SERVICE"])
        collected_at = datetime.combine(paid_date, time(6, index % 60))
        receipt = (receipt_id, f"RCP{receipt_id:010d}", member_id, branch_id, officer, paid_date, collected_at, channel, total, f"SYN-COL-{receipt_id:010d}", "POSTED", None, "SEED", officer, officer, collected_at)
        receipts.append(receipt)
        allocations.append((allocation_id, receipt_id, loan_id, sched_id, p_paid, c_paid, Decimal("0"), savings, Decimal("0"), paid_date, "SEED", officer, officer, collected_at, collected_at))
        if savings:
            savings_balances[member_id] += savings
            savings_txs.append((savings_tx_id, member_id, receipt_id, paid_date, "DEPOSIT", savings, savings_balances[member_id], "POSTED", "COLLECTION", officer, officer, collected_at, collected_at)); savings_tx_id += 1
        if receipt_id % 2500 == 0:
            original_receipts.append(receipt)
        receipt_id += 1; allocation_id += 1

    # Explicit linked reversal records preserve a realistic audit trail and reconcile at receipt level.
    for original in original_receipts:
        rev_date = min(original[5] + timedelta(days=1), AS_OF_DATE)
        amount = -original[8]
        collected_at = datetime.combine(rev_date, time(9))
        receipts.append((receipt_id, f"RCP{receipt_id:010d}", original[2], original[3], original[4], rev_date, collected_at, original[7], amount, f"SYN-REV-{receipt_id:010d}", "REVERSED", original[0], "SEED", original[4], original[4], collected_at))
        allocations.append((allocation_id, receipt_id, None, None, -original[8], Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), rev_date, "SEED", original[4], original[4], collected_at, collected_at))
        receipt_id += 1; allocation_id += 1

    # Independent deposits, withdrawals and interest make savings reporting useful beyond loan collections.
    for member_id in range(1, 5001):
        for sequence in range(1, 7):
            tx_date = date(2024 + (sequence + member_id) % 3, 1 + (member_id + sequence * 2) % 12, 1 + member_id % 24)
            if tx_date > AS_OF_DATE: continue
            amount = q(200 + (member_id + sequence) % 9 * 50)
            tx_type = "DEPOSIT"
            if sequence == 5 and savings_balances[member_id] >= amount:
                amount = -amount; tx_type = "WITHDRAWAL"
            elif sequence == 6:
                amount = q(max(Decimal("1"), savings_balances[member_id] * Decimal("0.01"))); tx_type = "INTEREST"
            savings_balances[member_id] += amount
            officer = refs["staff_by_branch"][(member_id * 17) % 50 + 1][5]
            at = datetime.combine(tx_date, time(7))
            savings_txs.append((savings_tx_id, member_id, None, tx_date, tx_type, amount, savings_balances[member_id], "POSTED", "SEED", officer, officer, at, at)); savings_tx_id += 1

    insert_many(cursor, "INSERT INTO collection_receipts VALUES (" + ",".join(["%s"] * 16) + ")", receipts)
    insert_many(cursor, "INSERT INTO collection_allocations VALUES (" + ",".join(["%s"] * 15) + ")", allocations)
    insert_many(cursor, "INSERT INTO savings_transactions VALUES (" + ",".join(["%s"] * 13) + ")", savings_txs)
    for batch in chunks([(balance, member_id) for member_id, balance in savings_balances.items()]):
        cursor.executemany("UPDATE savings_accounts SET current_balance=%s WHERE savings_account_id=%s", batch)

    snapshots = []
    snapshot_id = 1
    for loan_id, state in loan_state.items():
        current = month_end(state["disb"])
        # Keep snapshots strictly point-in-time: the latest closed reporting month is July 2026.
        final_month = month_end(add_months(AS_OF_DATE, -1))
        while current <= final_month:
            elapsed_days = max(0, (current - state["disb"]).days)
            total_days = max(1, (state["maturity"] - state["disb"]).days)
            remaining_ratio = Decimal(str(max(0, 1 - elapsed_days / total_days)))
            principal_out = q(state["principal"] * remaining_ratio)
            charge_out = q(state["charge"] * remaining_ratio)
            is_recent = current >= month_end(AS_OF_DATE - timedelta(days=90))
            bucket = state["bucket"] if is_recent else "CURRENT"
            classification = state["class"] if is_recent else "STANDARD"
            days = delinquency_for(loan_id) if is_recent else 0
            overdue = q((principal_out + charge_out) * Decimal("0.08")) if bucket != "CURRENT" else Decimal("0")
            status = state["status"] if current == final_month else "ACTIVE"
            item = state["item"]
            snapshots.append((snapshot_id, current, loan_id, item["member"]["id"], item["member"]["branch"], item["product"], item["officer"], principal_out, charge_out, overdue, days, bucket, classification, status, NOW_UTC)); snapshot_id += 1
            current = month_end(add_months(current, 1))
    insert_many(cursor, "INSERT INTO loan_monthly_snapshots VALUES (" + ",".join(["%s"] * 15) + ")", snapshots)
    return {"schedules": len(schedules), "receipts": len(receipts), "allocations": len(allocations), "savings_transactions": len(savings_txs), "snapshots": len(snapshots)}


def verify_invariants(cursor) -> dict[str, int]:
    checks = {
        "schedule_principal_mismatch": "SELECT COUNT(*) FROM (SELECT la.loan_id FROM loan_accounts la JOIN repayment_schedules rs ON rs.loan_id=la.loan_id GROUP BY la.loan_id, la.disbursed_amount HAVING ABS(SUM(rs.principal_due)-la.disbursed_amount) > 0.01) x",
        "receipt_allocation_mismatch": "SELECT COUNT(*) FROM (SELECT cr.receipt_id FROM collection_receipts cr JOIN collection_allocations ca ON ca.receipt_id=cr.receipt_id GROUP BY cr.receipt_id, cr.total_amount HAVING ABS(SUM(ca.principal_amount+ca.service_charge_amount+ca.penalty_amount+ca.savings_amount+ca.other_amount)-cr.total_amount) > 0.01) x",
        "negative_loan_balances": "SELECT COUNT(*) FROM loan_accounts WHERE principal_outstanding < 0 OR service_charge_outstanding < 0 OR overdue_amount < 0",
        "collection_before_disbursement": "SELECT COUNT(*) FROM collection_receipts cr JOIN collection_allocations ca ON ca.receipt_id=cr.receipt_id JOIN loan_accounts la ON la.loan_id=ca.loan_id WHERE cr.business_date < la.disbursement_date",
        "savings_balance_mismatch": "SELECT COUNT(*) FROM (SELECT sa.savings_account_id FROM savings_accounts sa LEFT JOIN savings_transactions st ON st.savings_account_id=sa.savings_account_id GROUP BY sa.savings_account_id, sa.current_balance HAVING ABS(COALESCE(SUM(st.amount),0)-sa.current_balance) > 0.01) x",
    }
    results = {}
    for name, sql in checks.items():
        cursor.execute(sql)
        results[name] = int(cursor.fetchone()[0])
    failed = {name: count for name, count in results.items() if count}
    if failed:
        raise RuntimeError(f"Financial invariant verification failed: {failed}")
    return results


def setup(reset: bool = False) -> dict[str, int]:
    prepare_database(reset)
    rng = random.Random(RANDOM_SEED)
    connection = server_connection(DATABASE_NAME)
    counts: dict[str, int] = {}
    try:
        with connection.cursor() as cursor:
            execute_sql_file(cursor, HERE / "schema_v1.sql")
            cursor.execute("INSERT INTO schema_metadata VALUES (1,%s,%s,%s,NULL,'SCHEMA_READY')", ("BRAC-inspired synthetic microfinance reporting demo", RANDOM_SEED, AS_OF_DATE))
            refs = seed_reference_data(cursor, rng)
            members = seed_members(cursor, rng, refs)
            seed_profile_updates(cursor, rng, members, refs)
            approved = seed_proposals(cursor, rng, members, refs)
            counts = seed_loans_and_transactions(cursor, rng, approved, refs)
            execute_sql_file(cursor, HERE / "views_v1.sql")
            verify_invariants(cursor)
            cursor.execute("UPDATE schema_metadata SET seeded_at_utc=%s, seed_status='COMPLETE' WHERE version_no=1", (NOW_UTC,))
            for table in ["members", "member_enrollments", "loan_proposals", "loan_accounts"]:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                counts[table] = int(cursor.fetchone()[0])
        connection.commit()
        return counts
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and seed the BRAC-inspired synthetic microfinance demo database.")
    parser.add_argument("--reset", action="store_true", help=f"Drop and rebuild only {DATABASE_NAME} if it already contains objects.")
    args = parser.parse_args()
    counts = setup(reset=args.reset)
    print(f"Created {DATABASE_NAME} through {AS_OF_DATE.isoformat()} with seed {RANDOM_SEED}.")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count:,}")


if __name__ == "__main__":
    main()
