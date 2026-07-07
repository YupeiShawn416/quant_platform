import uvicorn

from rq_platform.settings import settings


def main() -> None:
    uvicorn.run(
        "rq_platform.api.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=False,
    )


if __name__ == "__main__":
    main()
