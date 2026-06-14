import sys


SUPPORTED_MAJOR_MINOR = (3, 10)


def main() -> int:
    current = sys.version_info[:2]
    if current != SUPPORTED_MAJOR_MINOR:
        expected = ".".join(str(part) for part in SUPPORTED_MAJOR_MINOR)
        actual = ".".join(str(part) for part in sys.version_info[:3])
        print(f"PYTHON_VERSION_UNSUPPORTED expected={expected}.x actual={actual}", file=sys.stderr)
        return 1

    actual = ".".join(str(part) for part in sys.version_info[:3])
    print(f"PYTHON_VERSION_OK {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
