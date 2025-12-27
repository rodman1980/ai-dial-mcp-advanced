# ============================================================================
# User Information Models: Pydantic schemas for user service API contracts
# ============================================================================
# Defines the data structures for user creation, updates, and search operations.
# These models are used for:
# - Input validation in MCP tool schemas
# - Request/response serialization with the user service API
# - Auto-generation of JSON schemas for OpenAI/Claude tool invocation
# ============================================================================

from typing import Optional

from pydantic import BaseModel


class Address(BaseModel):
    """
    User residential address information.
    
    Attributes:
        country: Country name (e.g., "USA", "Belarus")
        city: City name
        street: Street name and number
        flat_house: Apartment/house number or identifier
    """
    country: str
    city: str
    street: str
    flat_house: str


class CreditCard(BaseModel):
    """
    User payment information for credit card processing.
    
    Attributes:
        num: Credit card number (full or masked)
        cvv: Card verification value/security code
        exp_date: Expiration date (format: MM/YY or similar)
    """
    num: str
    cvv: str
    exp_date: str


class UserCreate(BaseModel):
    """
    Schema for creating a new user via the user service API.
    
    Used by:
    - CreateUserTool.input_schema for OpenAI schema generation
    - UserClient.add_user() request validation
    
    Attributes:
        name: User's first name (required)
        surname: User's last name (required)
        email: User's email address (required, unique per service)
        phone: Contact phone number (optional)
        date_of_birth: Birth date in ISO format (optional)
        address: Residential address object (optional)
        gender: Gender identifier (optional)
        company: Current employer name (optional)
        salary: Annual salary amount (optional)
        about_me: User biography or description (required)
        credit_card: Payment information (optional)
    """
    name: str
    surname: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[Address] = None
    gender: Optional[str] = None
    company: Optional[str] = None
    salary: Optional[float] = None
    about_me: str
    credit_card: Optional[CreditCard] = None


class UserUpdate(BaseModel):
    """
    Schema for partial user updates via PATCH/PUT operations.
    
    Allows updating a subset of user fields while preserving existing values.
    All fields are optional to support flexible partial updates.
    
    Used by:
    - UpdateUserTool.input_schema for schema generation
    - UserClient.update_user() request payload validation
    
    Note: credit_card field accepts full UserCreate object for backward compatibility
    """
    name: Optional[str] = None
    surname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[Address] = None
    gender: Optional[str] = None
    company: Optional[str] = None
    salary: Optional[float] = None
    # Note: accepts UserCreate object for nested validation; field name mismatch (credit_card vs CreditCard type)
    # could be refactored to CreditCard type for consistency
    credit_card: Optional[UserCreate] = None


class UserSearchRequest(BaseModel):
    """
    Schema for user search/filter queries.
    
    Supports flexible filtering by individual fields. An empty request
    returns all users; non-empty fields act as AND filters.
    
    Used by:
    - SearchUsersTool.input_schema for schema generation
    - UserClient.search_users() request payload validation
    
    Attributes:
        name: Filter by first name (exact or partial match depends on service)
        email: Filter by email address (typically exact match)
        surname: Filter by last name
        gender: Filter by gender identifier
    """
    name: Optional[str] = None
    email: Optional[str] = None
    surname: Optional[str] = None
    gender: Optional[str] = None