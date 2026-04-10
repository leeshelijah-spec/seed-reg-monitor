from __future__ import annotations

import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import init_db
from app.services.refine_logic import RefineLogicService


def main() -> int:
    init_db()
    result = RefineLogicService().run(run_sync=True)

    print("[refinelogic] 실행 완료")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sync_status = (result.get("sync") or {}).get("status")
    if sync_status == "partial_failure":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
