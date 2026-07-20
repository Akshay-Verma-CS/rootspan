"""Console entry point for one role-configured incident-lab process."""

import os

import uvicorn

from rootspan.lab.app import LabConfig, LabRole, create_lab_app


def _default_port(role: LabRole) -> int:
    return {
        LabRole.GATEWAY: 9001,
        LabRole.CHECKOUT: 9002,
        LabRole.INVENTORY: 9003,
    }[role]


def main() -> None:
    config = LabConfig.from_environment()
    application = create_lab_app(config)
    uvicorn.run(
        application,
        host=os.getenv("LAB_HOST", "127.0.0.1"),
        port=int(os.getenv("LAB_PORT", str(_default_port(config.role)))),
    )


if __name__ == "__main__":
    main()
