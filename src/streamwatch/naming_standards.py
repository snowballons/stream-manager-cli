"""
Naming standards and conventions for StreamWatch application.

This module documents and enforces consistent naming conventions
throughout the codebase to improve readability and maintainability.
"""

import re
from typing import List, Tuple


class NamingStandards:
    """
    Naming standards and validation for StreamWatch codebase.
    """

    # Naming patterns
    SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
    CONSTANT_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
    CLASS_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9]*$")  # PascalCase
    PRIVATE_PATTERN = re.compile(r"^_[a-z][a-z0-9_]*$")
    DUNDER_PATTERN = re.compile(r"^__[a-z][a-z0-9_]*__$")

    @classmethod
    def validate_function_name(cls, name: str) -> bool:
        """Validate function name follows snake_case convention."""
        return bool(
            cls.SNAKE_CASE_PATTERN.match(name) or cls.PRIVATE_PATTERN.match(name)
        )

    @classmethod
    def validate_variable_name(cls, name: str) -> bool:
        """Validate variable name follows snake_case convention."""
        return bool(
            cls.SNAKE_CASE_PATTERN.match(name) or cls.PRIVATE_PATTERN.match(name)
        )

    @classmethod
    def validate_constant_name(cls, name: str) -> bool:
        """Validate constant name follows UPPER_CASE convention."""
        return bool(cls.CONSTANT_PATTERN.match(name))

    @classmethod
    def validate_class_name(cls, name: str) -> bool:
        """Validate class name follows PascalCase convention."""
        return bool(cls.CLASS_PATTERN.match(name))

    @classmethod
    def suggest_snake_case(cls, name: str) -> str:
        """Convert camelCase or PascalCase to snake_case."""
        # Insert underscore before uppercase letters (except first)
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        # Insert underscore before uppercase letters preceded by lowercase
        s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.lower()

    @classmethod
    def suggest_pascal_case(cls, name: str) -> str:
        """Convert snake_case to PascalCase."""
        components = name.split("_")
        return "".join(word.capitalize() for word in components)

    @classmethod
    def suggest_constant_case(cls, name: str) -> str:
        """Convert any case to CONSTANT_CASE."""
        snake_case = cls.suggest_snake_case(name)
        return snake_case.upper()


# Standard naming conventions used in StreamWatch
NAMING_CONVENTIONS = {
    # Functions and methods
    "functions": "snake_case",
    "methods": "snake_case",
    "private_methods": "_snake_case",
    # Variables
    "variables": "snake_case",
    "private_variables": "_snake_case",
    "constants": "UPPER_CASE",
    # Classes and types
    "classes": "PascalCase",
    "exceptions": "PascalCase",
    "enums": "PascalCase",
    "protocols": "PascalCase",
    # Files and modules
    "modules": "snake_case",
    "packages": "snake_case",
    # Database
    "table_names": "snake_case",
    "column_names": "snake_case",
    # Configuration
    "config_keys": "snake_case",
    "config_sections": "PascalCase",
    # API and JSON
    "json_keys": "snake_case",
    "api_endpoints": "kebab-case",
}


# Common naming patterns for StreamWatch domain
DOMAIN_NAMING_PATTERNS = {
    # Stream-related
    "stream_url": "URL of a stream",
    "stream_alias": "User-friendly name for a stream",
    "stream_info": "Complete stream information object",
    "stream_status": "Current status of a stream (live/offline/error)",
    "stream_metadata": "Additional stream data (title, category, etc.)",
    # User interface
    "ui_component": "User interface component",
    "menu_handler": "Handles menu interactions",
    "input_handler": "Processes user input",
    "display_manager": "Manages display output",
    # Data management
    "database_manager": "Manages database operations",
    "cache_manager": "Manages caching operations",
    "config_manager": "Manages configuration",
    "stream_manager": "Manages stream operations",
    # Processing
    "stream_checker": "Checks stream status",
    "metadata_fetcher": "Fetches stream metadata",
    "playback_controller": "Controls stream playback",
    "rate_limiter": "Limits request rates",
    # Validation and security
    "validator": "Validates input data",
    "sanitizer": "Sanitizes input data",
    "security_checker": "Performs security checks",
    # Results and responses
    "result": "Operation result (success/failure)",
    "response": "Response from external service",
    "status": "Current state of something",
    "error": "Error information",
}


def check_naming_consistency(code_text: str) -> List[Tuple[str, str, str]]:
    """
    Check code for naming consistency issues.

    Args:
        code_text: Source code to check

    Returns:
        List of (line, issue, suggestion) tuples
    """
    issues = []
    lines = code_text.split("\n")

    for i, line in enumerate(lines, 1):
        line = line.strip()

        # Check for camelCase in variable assignments
        camel_case_vars = re.findall(
            r"\b([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)\s*=", line
        )
        for var in camel_case_vars:
            suggestion = NamingStandards.suggest_snake_case(var)
            issues.append(
                (
                    f"Line {i}",
                    f"camelCase variable '{var}' should use snake_case",
                    f"Consider renaming to '{suggestion}'",
                )
            )

        # Check for inconsistent function names
        func_matches = re.findall(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)", line)
        for func_name in func_matches:
            if not NamingStandards.validate_function_name(func_name):
                suggestion = NamingStandards.suggest_snake_case(func_name)
                issues.append(
                    (
                        f"Line {i}",
                        f"Function name '{func_name}' should use snake_case",
                        f"Consider renaming to '{suggestion}'",
                    )
                )

    return issues


# Approved abbreviations for StreamWatch
APPROVED_ABBREVIATIONS = {
    "url": "URL",
    "api": "API",
    "ui": "UI",
    "db": "database",
    "config": "configuration",
    "auth": "authentication",
    "meta": "metadata",
    "info": "information",
    "mgr": "manager",
    "ctrl": "controller",
    "util": "utility",
    "impl": "implementation",
    "temp": "temporary",
    "max": "maximum",
    "min": "minimum",
    "num": "number",
    "str": "string",
    "int": "integer",
    "bool": "boolean",
    "dict": "dictionary",
    "list": "list",
    "obj": "object",
    "cls": "class",
    "func": "function",
    "var": "variable",
    "param": "parameter",
    "arg": "argument",
    "ret": "return",
    "err": "error",
    "exc": "exception",
    "req": "request",
    "resp": "response",
    "res": "result",
    "src": "source",
    "dst": "destination",
    "tmp": "temporary",
    "prev": "previous",
    "curr": "current",
    "next": "next",
    "idx": "index",
    "len": "length",
    "cnt": "count",
    "val": "value",
    "key": "key",
    "ref": "reference",
    "ptr": "pointer",
    "addr": "address",
    "conn": "connection",
    "sess": "session",
    "trans": "transaction",
    "proc": "process",
    "exec": "execute",
    "init": "initialize",
    "term": "terminate",
    "start": "start",
    "stop": "stop",
    "run": "run",
    "load": "load",
    "save": "save",
    "get": "get",
    "set": "set",
    "add": "add",
    "del": "delete",
    "upd": "update",
    "ins": "insert",
    "sel": "select",
    "find": "find",
    "search": "search",
    "sort": "sort",
    "filter": "filter",
    "map": "map",
    "reduce": "reduce",
    "fold": "fold",
    "zip": "zip",
    "iter": "iterator",
    "gen": "generator",
    "async": "asynchronous",
    "sync": "synchronous",
    "lock": "lock",
    "mutex": "mutex",
    "sem": "semaphore",
    "queue": "queue",
    "stack": "stack",
    "heap": "heap",
    "tree": "tree",
    "graph": "graph",
    "node": "node",
    "edge": "edge",
    "vertex": "vertex",
    "path": "path",
    "dir": "directory",
    "file": "file",
    "ext": "extension",
    "mime": "MIME type",
    "http": "HTTP",
    "https": "HTTPS",
    "tcp": "TCP",
    "udp": "UDP",
    "ip": "IP address",
    "dns": "DNS",
    "ssl": "SSL",
    "tls": "TLS",
    "json": "JSON",
    "xml": "XML",
    "html": "HTML",
    "css": "CSS",
    "js": "JavaScript",
    "sql": "SQL",
    "regex": "regular expression",
    "uuid": "UUID",
    "guid": "GUID",
    "id": "identifier",
    "pk": "primary key",
    "fk": "foreign key",
    "ttl": "time to live",
    "etl": "extract, transform, load",
    "crud": "create, read, update, delete",
    "rest": "REST",
    "soap": "SOAP",
    "rpc": "RPC",
    "cli": "command line interface",
    "gui": "graphical user interface",
    "tui": "text user interface",
    "os": "operating system",
    "fs": "file system",
    "vm": "virtual machine",
    "cpu": "CPU",
    "gpu": "GPU",
    "ram": "RAM",
    "rom": "ROM",
    "ssd": "SSD",
    "hdd": "HDD",
    "usb": "USB",
    "pci": "PCI",
    "bios": "BIOS",
    "uefi": "UEFI",
}
