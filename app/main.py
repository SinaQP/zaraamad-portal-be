from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(
        title="Zaraamad Portal API",
        description="Base FastAPI application scaffold.",
        version="0.1.0",
    )


app = create_app()
