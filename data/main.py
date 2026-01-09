import importlib
import logging
import pkgutil
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from sqlmodel import SQLModel

from core.config import settings
from core.database import create_all_tables, dispose_engine

logger = logging.getLogger(__name__)


def discover_and_load_plugins():
    """Dynamically discovers and loads all plugin packages in the 'plugins' directory."""

    # 1. Define the plugin package
    plugins_package = "plugins"
    plugin_routers = []
    plugin_models = []
    plugin_startups = []

    # 2. Browse all modules in the plugins package
    try:
        package = importlib.import_module(plugins_package)
        package_path = Path(package.__file__).parent
    except ImportError:
        logger.error(f"Package '{plugins_package}' not found. No plugins loaded.")
        return plugin_routers, plugin_models, plugin_startups

    # 3. Find all subpackages (plugin folders)
    for _, plugin_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
        if not is_pkg:
            continue  # Skip simple files

        full_plugin_name = f"{plugins_package}.{plugin_name}"
        logger.info(f"Loading plugin '{full_plugin_name}'")

        try:
            # 4. Try importing the plugin
            plugin_module = importlib.import_module(full_plugin_name)

            # 5. Check for standard API attributes (convention over configuration)
            if hasattr(plugin_module, 'router'):
                plugin_routers.append(plugin_module.router)
                logger.info(f"Router registered for plugin '{full_plugin_name}'")

            if hasattr(plugin_module, 'models'):
                # 'models' can be a list or a single module
                models = plugin_module.models
                if isinstance(models, list):
                    plugin_models.extend(models)
                else:
                    # If 'models' is a module, collect all SQLModel classes in it.
                    for attr_name in dir(models):
                        attr = getattr(models, attr_name)
                        if isinstance(attr, type) and issubclass(attr, SQLModel) and attr != SQLModel and hasattr(attr,
                                                                                                                  '__tablename__'):
                            plugin_models.append(attr)
                logger.info(f"Modules registered for plugin '{full_plugin_name}'")
            
            if hasattr(plugin_module, 'startup'):
                plugin_startups.append(plugin_module.startup)
                logger.info(f"Startup function registered for plugin '{full_plugin_name}'")

        except ImportError as e:
            # Isolate the error: A faulty plugin doesn't stop the entire app
            logger.error(f"Failed to load plugin '{full_plugin_name}': {e}")

    logger.info(f"Loaded {len(plugin_routers)} Plugin(s) successfully.")
    logger.info(f"Found routers: {[r.prefix for r in plugin_routers]}")
    logger.info(f"Found models: {[m.__name__ for m in plugin_models]}")
    return plugin_routers, plugin_models, plugin_startups


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    This function manages the app's lifecycle.
    Everything BEFORE the 'yield' happens at startup.
    Everything AFTER the 'yield' happens at shutdown.
    """

    # +++ STARTUP Logic +++
    logger.info(f"Starting up App '{settings.APP_NAME}'...")

    logger.info("Discovering plugins and registering models...")
    # 6. Dynamically load plugins
    plugin_routers, plugin_models, plugin_startups = discover_and_load_plugins()
    logger.info(f"Discovered {len(plugin_models)} model(s) from {len(plugin_routers)} plugin(s).")

    logger.info("Creating database tables...")
    # Creates all tables on startup.
    create_all_tables()
    logger.info("Database tables created.")

    logger.info("Registering plugin routers...")
    # 7. Add all found routers to the app
    for router in plugin_routers:
        app.include_router(router, prefix=settings.API_V1_STR)
    logger.info("Plugin routers registered.")

    logger.info("Running plugin startup checks...")
    for startup_func in plugin_startups:
        try:
            startup_func()
        except Exception as e:
            logger.error(f"Error during plugin startup: {e}")

    logger.info(f"App '{settings.APP_NAME}' successfully started.")

    # IMPORTANT: 'yield' hands over control to the running app
    yield

    # +++ SHUTDOWN logic +++
    logger.info(f"Shutting down App '{settings.APP_NAME}'...")
    dispose_engine()
    logger.info("Cleanup complete. Goodbye!")


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=app_lifespan, debug=settings.DEBUG,
              openapi_url=f"{settings.API_V1_STR}/openapi.json", docs_url=f"{settings.API_V1_STR}/docs",
              redoc_url=f"{settings.API_V1_STR}/redoc")


@app.get(settings.API_V1_STR + "/")
def root():
    return {"message": f"{settings.APP_NAME} is running", "api_prefix": settings.API_V1_STR}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Automatic dependency check at startup
def check_and_install_dependencies():
    """Check if plugin dependencies are installed."""
    try:
        from install_plugins import PluginDependencyInstaller
        installer = PluginDependencyInstaller(dry_run=False)
        # Prüfe nur, installiere nicht automatisch
        req_files = installer.find_plugin_requirements()
        if req_files:
            logger.info(f"Found {len(req_files)} plugin(s) with dependencies")
            # Optional: Hier könntest du den Benutzer fragen, ob installiert werden soll
    except ImportError:
        logger.warning("Plugin dependency checker not available")


if __name__ == "__main__":
    if settings.DEBUG:
        logging.basicConfig(level=logging.DEBUG)
        print(f"🚀 Starte {settings.APP_NAME} im DEBUG-Modus")
        print(f"   Host: {settings.HOST}, Port: {settings.PORT}")
        print(f"   Database: {settings.DATABASE_URL}")
    else:
        logging.basicConfig(level=logging.INFO)

    check_and_install_dependencies()

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=settings.DEBUG,
    )
