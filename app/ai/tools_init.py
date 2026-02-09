from app.ai.tool_registry import register_tool, ToolSpec

from app.services.find_materials_service import run_find_materials_pipeline
from app.services.view_notice_service import run_view_notices_pipeline
from app.services.cover_gen_service import run_cover_generator_pipeline
from app.services.check_marks_service import run_check_marks_pipeline  
from app.services.generate_marksheet_service import run_generate_marksheet_pipeline

def init_tools():
    register_tool(ToolSpec(name="find_materials", handler=run_find_materials_pipeline))
    register_tool(ToolSpec(name="view_notices", handler=run_view_notices_pipeline))
    register_tool(ToolSpec(name="generate_cover_page", handler=run_cover_generator_pipeline))
    register_tool(ToolSpec(name="check_marks", handler=run_check_marks_pipeline))
    register_tool(ToolSpec(name="generate_marksheet", handler=run_generate_marksheet_pipeline))
