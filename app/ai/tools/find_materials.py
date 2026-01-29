from app.ai.tool_registry import ToolSpec, register_tool, build_find_materials_system_prompt
from app.schemas.ai_schemas.find_materials_schemas import FindMaterialsLLMOutput
from app.services.material_service import find_materials_handler

def register_find_materials_tool():
    register_tool(
        ToolSpec(
            name="find_materials",
            system_prompt=build_find_materials_system_prompt(),
            output_model=FindMaterialsLLMOutput,
            handler=find_materials_handler,
        )
    )
