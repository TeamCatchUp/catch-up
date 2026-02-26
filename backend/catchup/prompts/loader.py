import logging
from pathlib import Path
from jinja2 import Environment, StrictUndefined, FileSystemLoader, TemplateNotFound


logger = logging.getLogger(__name__)

class PromptLoader:
    def __init__(self, template_dir: str | Path = None):
        
        if template_dir is None:
            self.template_dir = Path(__file__).parent.parent / "prompts"
        else:
            self.template_dir = Path(template_dir)
        
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            
            undefined=StrictUndefined,
            
            # 변수: {{ }} -> << >>
            variable_start_string='<<',
            variable_end_string='>>',
            
            # 블록: 기본값 사용
            block_start_string='{%', 
            block_end_string='%}',
                                    
            # 주석 태그: {# #} -> <# #>
            comment_start_string='<#',
            comment_end_string='#>'
        )
    
    def get_prompt(
        self,
        template_path: str,
        **kwargs
    ) -> str:
        """
            usage: get_prompt('rag/rewrite.j2') 
        """
        if not template_path.endswith('.j2'):
            file_name = f"{template_path}.j2"
        else:
            file_name = template_path
        
        try:
            template = self.env.get_template(file_name)
            return template.render(**kwargs)
        
        except TemplateNotFound:
            logger.error(f"Template not found: {file_name}")
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {self.template_dir / file_name}")
        
        except Exception as e:
            raise RuntimeError(f"프롬프트 렌더링 중 오류 발생 {file_name}: {e}")


prompt_loader = PromptLoader()