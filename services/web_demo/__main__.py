import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "services.web_demo.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8081")),
        reload=False,
    )
