"""Console entry point for the RootSpan API."""

import os

import uvicorn


def main() -> None:
    """Run the development API server."""
    uvicorn.run(
        "rootspan.api.app:app",
        host=os.getenv("ROOTSPAN_HOST", "127.0.0.1"),
        port=int(os.getenv("ROOTSPAN_PORT", "8001")),
        reload=False,
    )


if __name__ == "__main__":
    main()
