"""Run the Day 8 UI service."""

from __future__ import annotations

import logging
import os

import uvicorn
from dotenv import load_dotenv

from Lab_Assigment.day08_ui.app import app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [day08_ui] %(levelname)s %(message)s",
)

PORT = int(os.getenv("DAY08_UI_PORT", "11014"))


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
