import os
from typing import Any, Optional

import requests

from mcp_server.models.user_info import UserUpdate, UserCreate

# ============================================================================
# User Management Service Client: REST API wrapper for user operations
# ============================================================================
# Provides async interface to user microservice (Docker on port 8041).
# Converts REST responses to formatted strings for MCP tools.
# Uses Pydantic models for validation and schema generation.
# ============================================================================

USER_SERVICE_ENDPOINT = os.getenv("USERS_MANAGEMENT_SERVICE_URL", "http://localhost:8041")


class UserClient:
    """
    REST client for User Management Service.
    
    Wraps HTTP calls to user microservice and formats responses as strings
    for consumption by MCP tools. All methods are async (for API consistency)
    but use synchronous requests library internally (blocking I/O).
    
    **External I/O:** Makes HTTP requests to external microservice.
    Failures raise exceptions with HTTP status and response body.
    
    **Error Handling:** Non-2xx status codes raise Exception with details.
    Callers should handle and wrap exceptions appropriately.
    """

    def __user_to_string(self, user: dict[str, Any]):
        """
        Format single user dict as markdown code block for readability.
        
        Args:
            user: User object from REST API (dict with keys: id, name, email, etc.)
        
        Returns:
            str: Markdown code block (triple backticks) with formatted key-value pairs.
                 Example: ```\n  id: 123\n  name: John\n```
        
        Remarks:
            Used by get_user() and search_users() to format results for LLM consumption.
            Markdown formatting improves readability in tool call outputs.
        """
        user_str = "```\n"
        for key, value in user.items():
            user_str += f"  {key}: {value}\n"
        user_str += "```\n"

        return user_str

    def __users_to_string(self, users: list[dict[str, Any]]):
        """
        Format list of users as concatenated markdown code blocks.
        
        Args:
            users: List of user objects from REST API
        
        Returns:
            str: Multiple markdown code blocks concatenated with trailing newline.
                 Each user formatted via __user_to_string().
        
        Remarks:
            Used by search_users() when returning multiple results.
            Trailing newline improves readability in streaming SSE responses.
        """
        users_str = ""
        for value in users:
            users_str += self.__user_to_string(value)
        users_str += "\n"

        return users_str

    async def get_user(self, user_id: int) -> str:
        """
        Retrieve a single user by ID.
        
        **HTTP:** GET /v1/users/{user_id}
        **Success:** 200 OK with user object
        
        Args:
            user_id: User ID (numeric identifier from database)
        
        Returns:
            str: Formatted user object as markdown code block
        
        Raises:
            Exception: HTTP error with status code and response body
                      (e.g., "HTTP 404: Not Found")
        
        Remarks:
            Blocking I/O: uses requests.get() in async method.
            Consider: could add retry logic or timeout handling.
        """
        headers = {"Content-Type": "application/json"}

        response = requests.get(url=f"{USER_SERVICE_ENDPOINT}/v1/users/{user_id}", headers=headers)

        if response.status_code == 200:
            data = response.json()
            return self.__user_to_string(data)

        raise Exception(f"HTTP {response.status_code}: {response.text}")

    async def search_users(
            self,
            name: Optional[str] = None,
            surname: Optional[str] = None,
            email: Optional[str] = None,
            gender: Optional[str] = None,
    ) -> str:
        """
        Search for users by optional filters (name, surname, email, gender).
        
        **HTTP:** GET /v1/users/search?name=...&surname=...&email=...&gender=...
        **Success:** 200 OK with list of matching users
        
        Args:
            name: Filter by first name (optional, case-sensitive)
            surname: Filter by last name (optional, case-sensitive)
            email: Filter by email address (optional)
            gender: Filter by gender field (optional)
        
        Returns:
            str: Formatted list of matching users (one markdown block per user).
                 Also prints count of results to stdout for visibility.
        
        Raises:
            Exception: HTTP error with status code and response body
        
        Remarks:
            All filters are optional; empty filters return all users.
            Params dict only includes non-None values (sparse query params).
            Side-effect: prints result count to stdout (for debugging/monitoring).
        """
        headers = {"Content-Type": "application/json"}

        # Build query params dict, only including non-None filters
        params = {}
        if name:
            params["name"] = name
        if surname:
            params["surname"] = surname
        if email:
            params["email"] = email
        if gender:
            params["gender"] = gender

        response = requests.get(url=USER_SERVICE_ENDPOINT + "/v1/users/search", headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            # Side-effect: print count for observability
            print(f"Get {len(data)} users successfully")
            return self.__users_to_string(data)

        raise Exception(f"HTTP {response.status_code}: {response.text}")

    async def add_user(self, user_create_model: UserCreate) -> str:
        """
        Create a new user.
        
        **HTTP:** POST /v1/users with UserCreate payload
        **Success:** 201 Created with user ID in response
        
        Args:
            user_create_model: Pydantic UserCreate instance with validated fields
                              (name, email, about_me required; others optional)
        
        Returns:
            str: Success message with response body (typically includes created user ID)
        
        Raises:
            Exception: HTTP error with status code and response body
                      (e.g., "HTTP 400: Validation failed")
        
        Remarks:
            Uses Pydantic model_dump() to serialize to JSON.
            Pydantic validation ensures schema compliance before sending.
            Response body content depends on microservice implementation.
        """
        headers = {"Content-Type": "application/json"}

        response = requests.post(
            url=f"{USER_SERVICE_ENDPOINT}/v1/users",
            headers=headers,
            json=user_create_model.model_dump()
        )

        if response.status_code == 201:
            return f"User successfully added: {response.text}"

        raise Exception(f"HTTP {response.status_code}: {response.text}")

    async def update_user(self, user_id: int, user_update_model: UserUpdate) -> str:
        """
        Update an existing user's information.
        
        **HTTP:** PUT /v1/users/{user_id} with UserUpdate payload
        **Success:** 201 Created (note: should ideally be 200 OK, but service returns 201)
        
        Args:
            user_id: ID of user to update
            user_update_model: Pydantic UserUpdate instance with optional fields
                              (all fields nullable for partial updates)
        
        Returns:
            str: Success message with response body
        
        Raises:
            Exception: HTTP error with status code and response body
                      (e.g., "HTTP 404: User not found")
        
        Remarks:
            Uses Pydantic model_dump() to serialize, includes null fields.
            Service returns 201 (unusual for PUT); consider 200 OK for RESTful compliance.
            TODO: Consider validating user_id exists before calling.
        """
        headers = {"Content-Type": "application/json"}

        response = requests.put(
            url=f"{USER_SERVICE_ENDPOINT}/v1/users/{user_id}",
            headers=headers,
            json=user_update_model.model_dump()
        )

        if response.status_code == 201:
            return f"User successfully updated: {response.text}"

        raise Exception(f"HTTP {response.status_code}: {response.text}")

    async def delete_user(self, user_id: int) -> str:
        """
        Delete a user by ID.
        
        **HTTP:** DELETE /v1/users/{user_id}
        **Success:** 204 No Content (response body empty)
        
        Args:
            user_id: ID of user to delete
        
        Returns:
            str: Success message (no response body from service)
        
        Raises:
            Exception: HTTP error with status code and response body
                      (e.g., "HTTP 404: User not found")
        
        Remarks:
            Service returns 204 (standard for DELETE).
            TODO: Consider soft deletes (mark deleted flag) vs. hard deletes.
        """
        headers = {"Content-Type": "application/json"}

        response = requests.delete(url=f"{USER_SERVICE_ENDPOINT}/v1/users/{user_id}", headers=headers)

        if response.status_code == 204:
            return "User successfully deleted"

        raise Exception(f"HTTP {response.status_code}: {response.text}")
