#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备连接缓存管理器
用于保存和加载之前成功连接的设备信息，提升设备连接速度
"""

import json
import os
import time
from typing import Dict, List, Optional, Tuple


class DeviceCache:
    """设备缓存管理类"""
    
    def __init__(self, cache_file: str = "device_cache.json"):
        """
        初始化设备缓存管理器
        
        Args:
            cache_file: 缓存文件路径，默认为 "device_cache.json"
        """
        self.cache_file = cache_file
        self.cache_data = self._load_cache()
        
    def _load_cache(self) -> Dict:
        """从文件加载缓存数据"""
        if not os.path.exists(self.cache_file):
            print(f"缓存文件 {self.cache_file} 不存在，创建新的缓存")
            return {
                "devices": [],
                "last_updated": None,
                "version": "1.0"
            }
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"成功加载缓存文件，包含 {len(data.get('devices', []))} 个设备")
                return data
        except Exception as e:
            print(f"加载缓存文件失败: {e}")
            return {
                "devices": [],
                "last_updated": None,
                "version": "1.0"
            }
    
    def _save_cache(self) -> bool:
        """保存缓存数据到文件"""
        try:
            # 更新最后修改时间
            self.cache_data["last_updated"] = time.time()
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
            
            print(f"缓存已保存到 {self.cache_file}")
            return True
        except Exception as e:
            print(f"保存缓存文件失败: {e}")
            return False
    
    def add_device(self, resource: str, idn: str, additional_info: Optional[Dict] = None) -> bool:
        """
        添加设备到缓存
        
        Args:
            resource: 设备的VISA资源地址
            idn: 设备的IDN响应
            additional_info: 额外的设备信息
            
        Returns:
            bool: 是否成功添加
        """
        # 检查设备是否已存在
        for device in self.cache_data["devices"]:
            if device["resource"] == resource:
                # 更新现有设备信息
                device["idn"] = idn
                device["last_connected"] = time.time()
                device["connection_count"] = device.get("connection_count", 0) + 1
                if additional_info:
                    device["additional_info"] = additional_info
                print(f"更新缓存中的设备: {resource}")
                return self._save_cache()
        
        # 添加新设备
        device_info = {
            "resource": resource,
            "idn": idn,
            "first_connected": time.time(),
            "last_connected": time.time(),
            "connection_count": 1,
            "success_rate": 1.0,  # 成功连接率
            "additional_info": additional_info or {}
        }
        
        self.cache_data["devices"].append(device_info)
        print(f"添加新设备到缓存: {resource}")
        return self._save_cache()
    
    def get_cached_devices(self) -> List[Dict]:
        """
        获取所有缓存的设备
        按最近连接时间排序
        
        Returns:
            List[Dict]: 缓存的设备列表
        """
        devices = self.cache_data.get("devices", []).copy()
        # 按最近连接时间排序
        devices.sort(key=lambda x: x.get("last_connected", 0), reverse=True)
        return devices
    
    def get_priority_devices(self, limit: int = 5) -> List[Dict]:
        """
        获取优先连接的设备（基于连接频率和成功率）
        
        Args:
            limit: 返回设备的最大数量
            
        Returns:
            List[Dict]: 优先设备列表
        """
        devices = self.cache_data.get("devices", []).copy()
        
        # 计算优先级分数：连接次数 * 成功率 + 最近连接时间权重
        current_time = time.time()
        for device in devices:
            last_connected = device.get("last_connected", 0)
            connection_count = device.get("connection_count", 1)
            success_rate = device.get("success_rate", 1.0)
            
            # 时间权重：最近7天内连接过的设备加分
            time_weight = 1.0 if (current_time - last_connected) < 7 * 24 * 3600 else 0.5
            
            device["priority_score"] = connection_count * success_rate * time_weight
        
        # 按优先级分数排序
        devices.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        return devices[:limit]
    
    def update_connection_result(self, resource: str, success: bool) -> bool:
        """
        更新设备连接结果统计
        
        Args:
            resource: 设备的VISA资源地址
            success: 连接是否成功
            
        Returns:
            bool: 是否成功更新
        """
        for device in self.cache_data["devices"]:
            if device["resource"] == resource:
                if success:
                    device["last_connected"] = time.time()
                
                # 更新成功率（使用简单的移动平均）
                current_success_rate = device.get("success_rate", 1.0)
                total_attempts = device.get("total_attempts", 1)
                
                if success:
                    new_success_rate = (current_success_rate * total_attempts + 1) / (total_attempts + 1)
                else:
                    new_success_rate = (current_success_rate * total_attempts) / (total_attempts + 1)
                
                device["success_rate"] = max(new_success_rate, 0.01)  # 最低1%成功率
                device["total_attempts"] = total_attempts + 1
                
                return self._save_cache()
        
        return False
    
    def remove_device(self, resource: str) -> bool:
        """
        从缓存中移除设备
        
        Args:
            resource: 设备的VISA资源地址
            
        Returns:
            bool: 是否成功移除
        """
        original_count = len(self.cache_data["devices"])
        self.cache_data["devices"] = [
            device for device in self.cache_data["devices"] 
            if device["resource"] != resource
        ]
        
        if len(self.cache_data["devices"]) < original_count:
            print(f"从缓存中移除设备: {resource}")
            return self._save_cache()
        
        return False
    
    def clear_cache(self) -> bool:
        """
        清空所有缓存
        
        Returns:
            bool: 是否成功清空
        """
        self.cache_data = {
            "devices": [],
            "last_updated": time.time(),
            "version": "1.0"
        }
        print("已清空设备缓存")
        return self._save_cache()
    
    def get_cache_stats(self) -> Dict:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 缓存统计信息
        """
        devices = self.cache_data.get("devices", [])
        if not devices:
            return {
                "total_devices": 0,
                "last_updated": None,
                "avg_success_rate": 0,
                "most_used_device": None
            }
        
        total_devices = len(devices)
        avg_success_rate = sum(d.get("success_rate", 0) for d in devices) / total_devices
        most_used_device = max(devices, key=lambda x: x.get("connection_count", 0))
        
        return {
            "total_devices": total_devices,
            "last_updated": self.cache_data.get("last_updated"),
            "avg_success_rate": avg_success_rate,
            "most_used_device": most_used_device["resource"]
        }
    
    def export_cache(self, export_file: str) -> bool:
        """
        导出缓存到指定文件
        
        Args:
            export_file: 导出文件路径
            
        Returns:
            bool: 是否成功导出
        """
        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
            print(f"缓存已导出到 {export_file}")
            return True
        except Exception as e:
            print(f"导出缓存失败: {e}")
            return False
