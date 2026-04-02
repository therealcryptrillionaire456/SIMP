from pydantic import BaseModel, Field
from typing import List, Optional

class IntentSchema(BaseModel):
    name: str = Field(..., description="The name of the intent.")
    description: Optional[str] = Field(None, description="A brief description of the intent.")
    examples: List[str] = Field(..., description="A list of example phrases for the intent.")

class SIMPIntent(BaseModel):
    intents: List[IntentSchema] = Field(..., description="A list of intents in the SIMP model.")