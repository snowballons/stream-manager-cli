"""
Dependency Injection Container for StreamWatch Application

This module provides a simple dependency injection container that manages
the creation and lifecycle of application dependencies, improving testability
and maintainability.
"""

import logging
from typing import Any, Callable, Dict, TypeVar

from . import config

logger = logging.getLogger(config.APP_NAME + ".container")

T = TypeVar("T")


class DIContainer:
    """
    Simple Dependency Injection Container for managing application dependencies.

    This container supports:
    - Singleton pattern for shared instances
    - Factory pattern for creating new instances
    - Lazy initialization
    - Dependency resolution
    """

    def __init__(self) -> None:
        """Initialize the DI container."""
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._singletons: Dict[str, Any] = {}
        self._singleton_factories: Dict[str, Callable[[], Any]] = {}
        self.logger = logging.getLogger(f"{config.APP_NAME}.container")

    def register_singleton(self, service_name: str, factory: Callable[[], T]) -> None:
        """
        Register a singleton service with a factory function.

        The factory will be called only once, and the same instance will be
        returned for all subsequent requests.

        Args:
            service_name: Name to register the service under
            factory: Factory function that creates the service instance
        """
        self._singleton_factories[service_name] = factory
        self.logger.debug(f"Registered singleton factory for '{service_name}'")

    def register_factory(self, service_name: str, factory: Callable[[], T]) -> None:
        """
        Register a factory service.

        The factory will be called each time the service is requested,
        returning a new instance each time.

        Args:
            service_name: Name to register the service under
            factory: Factory function that creates service instances
        """
        self._factories[service_name] = factory
        self.logger.debug(f"Registered factory for '{service_name}'")

    def register_instance(self, service_name: str, instance: T) -> None:
        """
        Register a pre-created instance as a singleton.

        Args:
            service_name: Name to register the service under
            instance: Pre-created instance to register
        """
        self._singletons[service_name] = instance
        self.logger.debug(f"Registered instance for '{service_name}'")

    def get(self, service_name: str) -> Any:
        """
        Get a service instance by name.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            The service instance

        Raises:
            KeyError: If the service is not registered
        """
        # Check if it's already a created singleton
        if service_name in self._singletons:
            return self._singletons[service_name]

        # Check if it's a singleton factory
        if service_name in self._singleton_factories:
            self.logger.debug(f"Creating singleton instance for '{service_name}'")
            instance = self._singleton_factories[service_name]()
            self._singletons[service_name] = instance
            return instance

        # Check if it's a regular factory
        if service_name in self._factories:
            self.logger.debug(f"Creating new instance for '{service_name}'")
            return self._factories[service_name]()

        # Check if it's a pre-registered service
        if service_name in self._services:
            return self._services[service_name]

        raise KeyError(f"Service '{service_name}' is not registered in the container")

    def has(self, service_name: str) -> bool:
        """
        Check if a service is registered.

        Args:
            service_name: Name of the service to check

        Returns:
            True if the service is registered, False otherwise
        """
        return (
            service_name in self._services
            or service_name in self._factories
            or service_name in self._singletons
            or service_name in self._singleton_factories
        )

    def clear(self) -> None:
        """Clear all registered services and instances."""
        self.logger.debug("Clearing all services from container")
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self._singleton_factories.clear()

    def get_registered_services(self) -> Dict[str, str]:
        """
        Get a list of all registered services and their types.

        Returns:
            Dictionary mapping service names to their registration types
        """
        services = {}

        for name in self._services:
            services[name] = "service"
        for name in self._factories:
            services[name] = "factory"
        for name in self._singletons:
            services[name] = "singleton_instance"
        for name in self._singleton_factories:
            services[name] = "singleton_factory"

        return services

    def __str__(self) -> str:
        """String representation of the container."""
        services = self.get_registered_services()
        return f"DIContainer(services={len(services)}: {list(services.keys())})"


class ServiceRegistry:
    """
    Service registry that provides a convenient way to configure
    the dependency injection container with all application services.
    """

    @staticmethod
    def configure_container(container: DIContainer) -> None:
        """
        Configure the DI container with all application services.

        Args:
            container: The DI container to configure
        """
        from .commands import CommandInvoker
        from .menu_handler import MenuHandler
        from .playback_controller import PlaybackController
        from .stream_checker import StreamChecker
        from .stream_manager import StreamManager

        logger.info("Configuring DI container with application services")

        # Register core services as singletons
        container.register_singleton("command_invoker", lambda: CommandInvoker())

        # Register the enhanced database as a singleton
        from .enhanced_database import create_enhanced_database

        container.register_singleton("database", lambda: create_enhanced_database())

        # Register StreamChecker with dependencies
        def create_stream_checker():
            try:
                from .cache import get_cache

                cache = get_cache()
            except ImportError:
                cache = None

            try:
                from .rate_limiter import get_rate_limiter

                rate_limiter = get_rate_limiter()
            except ImportError:
                rate_limiter = None

            return StreamChecker(cache=cache, rate_limiter=rate_limiter)

        container.register_singleton("stream_checker", create_stream_checker)

        # Register StreamManager and inject the enhanced database
        container.register_singleton(
            "stream_manager", lambda: StreamManager(database=container.get("database"))
        )

        container.register_singleton(
            "playback_controller", lambda: PlaybackController()
        )

        # MenuHandler depends on CommandInvoker, so we need to inject it
        def create_menu_handler():
            command_invoker = container.get("command_invoker")
            return MenuHandler(command_invoker=command_invoker)

        container.register_singleton("menu_handler", create_menu_handler)

        logger.info("DI container configuration completed")


__all__ = [
    "DIContainer",
    "ServiceRegistry",
]
