"""Request and response schemas for the strategy agent."""

from pydantic import BaseModel, Field


class UploadDocumentRequest(BaseModel):
    """Request to upload a document to strategy agent."""

    content: str = Field(..., description="Document content to store")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class UploadDocumentResponse(BaseModel):
    """Response after uploading a document."""

    success: bool


class AskRequest(BaseModel):
    """Request to ask the strategy agent a question."""

    question: str = Field(..., description="Question to ask")


class AskResponse(BaseModel):
    """Response from strategy agent."""

    response: str


class SearchDocumentsResponse(BaseModel):
    """Response with searched documents."""

    documents: list[str]


class HealthResponse(BaseModel):
    """Health check for strategy agent."""

    status: str
    agent_exists: bool
