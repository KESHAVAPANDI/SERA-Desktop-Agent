from pathlib import Path
import yaml


class SERAConfig:

    def __init__(self, path: str | None = None):

        if path is None:
            path = (
                Path(__file__).resolve()
                .parents[2]
                / "config"
                / "config.yaml"
            )

        self.path = Path(path)

        if not self.path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self.path}"
            )

        with open(
            self.path,
            "r",
            encoding="utf-8",
        ) as file:

            self.data = yaml.safe_load(file) or {}

    @property
    def assistant_name(self) -> str:

        return self.data.get(
            "assistant",
            {},
        ).get(
            "name",
            "SERA",
        )

    def model_config(
        self,
        role: str,
    ) -> dict:

        models = self.data.get(
            "models",
            {},
        )

        if role not in models:

            raise KeyError(
                f"Model role '{role}' "
                f"not found in config."
            )

        return models[role]

    def provider_name(
        self,
        role: str,
    ) -> str:

        return self.model_config(
            role
        )["provider"]

    def get(
        self,
        key: str,
        default: any = None,
    ):
        return self.data.get(key, default)

    def model_name(
        self,
        role: str,
    ) -> str:

        return self.model_config(
            role
        )["model"]


def load_config(path: str | None = None) -> dict:
    return SERAConfig(path).data