import sys


if __name__ == "__main__":
    # Packaged GUI executables have no console. Test failures must produce a
    # machine-readable report rather than an unattended PyInstaller dialog.
    try:
        from ai_memory_app.app import main
        raise SystemExit(main())
    except Exception:
        if "--test-report" not in sys.argv:
            raise
        import json
        import traceback
        from pathlib import Path
        report = Path(sys.argv[sys.argv.index("--test-report") + 1])
        report.write_text(json.dumps({"passed": False, "error": traceback.format_exc()}), encoding="utf-8")
        raise SystemExit(1)
