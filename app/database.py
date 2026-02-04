from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from app.config import get_settings


class Database:
    def __init__(self):
        self.regwatch_client = None
        self.ecosystem_client = None
        self.regwatch_db = None
        self.ecosystem_db = None
    
    async def connect(self):
        """Connect to both MongoDB databases"""
        settings = get_settings()
        
        # RegWatch Staging connection
        self.regwatch_client = AsyncIOMotorClient(
            settings.REGWATCH_MONGODB_URI,
            server_api=ServerApi('1')
        )
        self.regwatch_db = self.regwatch_client.regwatch_staging
        
        # Ecosystem connection
        self.ecosystem_client = AsyncIOMotorClient(
            settings.ECOSYSTEM_MONGODB_URI,
            server_api=ServerApi('1')
        )
        self.ecosystem_db = self.ecosystem_client.rtbe
        
        # Test connections
        await self.regwatch_client.admin.command('ping')
        await self.ecosystem_client.admin.command('ping')
        print("✅ Connected to RegWatch Staging database")
        print("✅ Connected to Ecosystem database")
    
    async def close(self):
        """Close both database connections"""
        if self.regwatch_client:
            self.regwatch_client.close()
        if self.ecosystem_client:
            self.ecosystem_client.close()
        print("❌ Database connections closed")
    
    def get_regwatch_collection(self, collection_name: str):
        """Get a collection from RegWatch database"""
        return self.regwatch_db[collection_name]
    
    def get_ecosystem_collection(self, collection_name: str):
        """Get a collection from Ecosystem database"""
        return self.ecosystem_db[collection_name]


# Global database instance
db = Database()


# Collections
def get_regwatch_company_supplements():
    """Get regwatch_company_supplements collection"""
    return db.get_regwatch_collection("regwatch_company_supplements")


def get_ecosystem_companies():
    """Get ecosystemcompanies collection"""
    return db.get_ecosystem_collection("ecosystemcompanies")


def get_regulations():
    """Get regulation_v3 collection"""
    return db.get_regwatch_collection("regulation_v3")


def get_pre_assessments():
    """Get pre-assessments collection"""
    return db.get_regwatch_collection("pre-assessments")

