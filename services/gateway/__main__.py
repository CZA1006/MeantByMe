import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "services.gateway.app:app",
        host="127.0.0.1",
        port=8000,
        access_log=False,
    )
