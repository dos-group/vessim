from .api import router, startup
from .models import EntsoePrice

# IMPORTANT: These variables are searched for by discover_and_load_plugins()
router = router
models = [EntsoePrice] # List of SQLModel classes
startup = startup