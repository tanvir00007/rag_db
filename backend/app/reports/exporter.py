from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.settings import settings


def export_report(rows: list[dict[str, Any]], title: str | None = None) -> tuple[str, str]:
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(ch.lower() if ch.isalnum() else "_" for ch in (title or "report")).strip("_")
    stem = f"{safe_title or 'report'}_{stamp}"
    csv_path: Path = settings.exports_dir / f"{stem}.csv"
    xlsx_path: Path = settings.exports_dir / f"{stem}.xlsx"

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Report", index=False)
    return f"/api/reports/{csv_path.name}", f"/api/reports/{xlsx_path.name}"

