from rq_platform.data_sources.rqdata_source import RQDataSource
from rq_platform.settings import settings


def main() -> None:
    print("=== RQData connection check ===")
    print("settings loaded: ok")
    print(f"license exists: {'yes' if bool(settings.rqdata_license) else 'no'}")

    source = RQDataSource()

    print("\n=== RQData info ===")
    try:
        print(source.info())
    except Exception as exc:
        print(f"connection failed: {type(exc).__name__}: {exc}")
        raise

    print("\n=== RQData quota ===")
    print(source.quota())


if __name__ == "__main__":
    main()
