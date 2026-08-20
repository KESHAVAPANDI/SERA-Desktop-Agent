import asyncio

from dotenv import load_dotenv

from app.core.assistant import SERA


def main():

    load_dotenv()

    sera = SERA()

    asyncio.run(
        sera.run()
    )


if __name__ == "__main__":
    main()