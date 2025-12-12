#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
排行榜数据清洗模块
用于处理排行榜数据，将其转换为指定格式："用户排名/总人数，学号，名字"
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# 使用统一的绝对路径配置
from paths import RANK_RECORD_DIR
from ..core.logger_manager import setup_logger

logger = setup_logger("rank_cleaner")


class RankDataCleaner:
    """排行榜数据清洗器"""
    
    def __init__(self):
        """初始化排行榜数据清洗器"""
        self.logger = logger
    
    def load_rank_data(self, file_path: str) -> Dict[str, Any]:
        """
        从JSON文件加载排行榜数据
        
        Args:
            file_path: 排行榜数据文件路径
            
        Returns:
            解析后的排行榜数据字典
            
        Raises:
            FileNotFoundError: 文件不存在
            json.JSONDecodeError: JSON格式错误
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"排行榜数据文件不存在: {file_path}")
        
        try:
            with path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.logger.info(f"成功加载排行榜数据: {file_path}")
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f"排行榜数据JSON格式错误: {e}")
            raise
    
    def clean_rank_data(self, data: Dict[str, Any]) -> List[str]:
        """
        清洗排行榜数据，转换为指定格式
        
        Args:
            data: 原始排行榜数据
            
        Returns:
            清洗后的数据列表，每项格式为："用户排名/总人数，学号，名字"
        """
        if not isinstance(data, dict):
            raise ValueError("排行榜数据必须是字典格式")
        
        total = data.get('total', 0)
        rows = data.get('rows', [])
        
        if not isinstance(total, int) or total <= 0:
            raise ValueError("总人数必须大于0")
        
        if not isinstance(rows, list):
            raise ValueError("排行榜行数据必须是列表格式")
        
        cleaned_data = []
        
        for index, row in enumerate(rows, 1):
            try:
                # 使用从1开始的连续排名，忽略原始数据中的ranking值
                ranking = index
                student_id = row.get('studentId', '')
                student_name = row.get('studentName', '')
                
                if not student_id or not student_name:
                    self.logger.warning(f"跳过无效数据行: {row}")
                    continue
                
                # 格式："用户排名/总人数，学号，名字"
                formatted_line = f"{ranking}/{total}，{student_id}，{student_name}"
                cleaned_data.append(formatted_line)
                
                self.logger.debug(f"处理数据: {formatted_line}")
                
            except Exception as e:
                self.logger.error(f"处理数据行时出错: {row}, 错误: {e}")
                continue
        
        self.logger.info(f"成功清洗 {len(cleaned_data)} 条排行榜数据")
        return cleaned_data
    
    def save_cleaned_data(self, cleaned_data: List[str], output_file: str) -> None:
        """
        保存清洗后的数据到文件
        
        Args:
            cleaned_data: 清洗后的数据列表
            output_file: 输出文件路径
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with output_path.open('w', encoding='utf-8') as f:
                for line in cleaned_data:
                    f.write(line + '\n')
            
            self.logger.info(f"清洗后的数据已保存到: {output_file}")
        except Exception as e:
            self.logger.error(f"保存清洗数据时出错: {e}")
            raise
    
    def process_rank_file(self, input_file: str, output_file: Optional[str] = None) -> List[str]:
        """
        处理排行榜文件的完整流程
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径，如果为None则自动生成
            
        Returns:
            清洗后的数据列表
        """
        # 加载原始数据
        raw_data = self.load_rank_data(input_file)
        
        # 清洗数据
        cleaned_data = self.clean_rank_data(raw_data)
        
        # 确定输出文件路径
        if output_file is None:
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_cleaned.txt")
        
        # 保存清洗后的数据
        self.save_cleaned_data(cleaned_data, output_file)
        
        return cleaned_data


def clean_rank_data_file(input_file: str, output_file: Optional[str] = None) -> List[str]:
    """
    便捷函数：清洗排行榜数据文件
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径，如果为None则自动生成
        
    Returns:
        清洗后的数据列表
    """
    cleaner = RankDataCleaner()
    return cleaner.process_rank_file(input_file, output_file)


def main():
    """
    主函数：处理指定日期的排行榜数据
    """
    # 默认处理今天的排行榜数据
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    input_file = str(RANK_RECORD_DIR / f"{today}.txt")
    
    try:
        cleaned_data = clean_rank_data_file(input_file)
        print(f"排行榜数据清洗完成，共处理 {len(cleaned_data)} 条记录")
        
        # 显示前5条数据作为示例
        for i, line in enumerate(cleaned_data[:5]):
            print(f"示例 {i+1}: {line}")
            
    except FileNotFoundError:
        print(f"未找到排行榜数据文件: {input_file}")
        print("请确保文件存在或提供正确的文件路径")
    except Exception as e:
        print(f"处理排行榜数据时出错: {e}")


if __name__ == "__main__":
    main()
