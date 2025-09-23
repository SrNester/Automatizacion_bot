class SalesforceService:
    async def health_check(self):
        return {"status": "healthy", "provider": "salesforce"}
    
    async def find_contact_by_email(self, email: str):
        return {"success": False, "contact": None}
    
    async def find_contact_by_phone(self, phone: str):
        return {"success": False, "contact": None}
    
    async def create_contact(self, data: dict):
        return {"success": True, "contact_id": "sf_dummy_id"}
    
    async def update_contact(self, contact_id: str, data: dict):
        return {"success": True}