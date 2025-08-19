import pyvisa
import time
import numpy as np

rm = pyvisa.ResourceManager()

class PM100D:
    """
    此类用于通过 USB (VISA) 连接控制 Thorlabs PM100D 光功率/能量计。

    初始化变量 (Initialization Variables):
    resourceLoc:      包含 VISA 资源地址的字符串。通常可以自动找到，
                      但也可以手动指定，例如 'USB0::0x1313::0x8070::P0000116::INSTR'。

    实例变量 (Variables):
    .inst:            一个包含 pyVISA 连接到 PM100D 硬件的容器。
    .bw:              一个字典，将带宽名称 ('HI', 'LO') 转换为其在 PM100D 串行命令中的对应索引。
    .bandwidth:       一个字符串，表示当前的光电二极管带宽设置 ('HI' 或 'LO')。
    .wavelength:      一个浮点数，表示当前的波长校正值，单位为纳米 (nm)。
    .avg_count:       一个整数，表示当前的平均采样次数。

    方法 (Methods):
    .setWavelength(nm):         设置波长校正值，单位 nm。
    .getWavelength():           返回当前的波长校正值 (nm)。
    .setBandwidth(name):        设置光电二极管带宽，name 必须是 'HI' 或 'LO'。
    .getBandwidth():            返回当前的带宽设置 ('HI' 或 'LO')。
    .setAvgCount(count):        设置平均采样次数。
    .getAvgCount():            返回当前的平均采样次数。
    .setRangeAuto(auto_on):     设置功率测量的自动量程。auto_on 为 True 或 False。
    .getRangeAuto():            返回自动量程是否开启。
    .getPower():                返回一个浮点数，表示当前的功率测量值，单位为瓦特 (W)。
    .getSensorInfo():           返回一个字典，包含当前连接的传感器的信息。
    .zero():                    执行清零（背景校准）操作。
    .write(message, q):         pyVISA inst.query() 或 inst.write() 的封装。
    .close():                  关闭与 PM100D 的 pyVISA 连接。
    """
    type = "PM100D"

    def __init__(self, resourceLoc=None):
        """
        初始化并连接到 PM100D。
        """
        try:
            self.inst = rm.open_resource(resourceLoc)
            self.inst.timeout = 2000 # 设置超时为 2000 ms
            print("已连接到: ", self.inst.query("*IDN?").strip())
        except Exception as e:
            print(f"连接到 PM100D 时出错: {e}")
            print("请检查连接和 VISA 驱动程序，然后重试。")
            raise e

        # 带宽设置映射
        self.bw = {"HI": "1", "LO": "0"}
        
        # 初始化实例变量以匹配设备当前状态
        self.wavelength = self.getWavelength()
        self.bandwidth = self.getBandwidth()
        self.avg_count = self.getAvgCount()

    def setWavelength(self, nm=1550):
        """设置波长校正值，单位为纳米 (nm)。"""
        self.inst.write(f"SENS:CORR:WAV {int(nm)}")
        self.wavelength = int(nm)

    def getWavelength(self):
        """返回当前的波长校正值 (nm)。"""
        return float(self.inst.query("SENS:CORR:WAV?"))

    def setBandwidth(self, name="LO"):
        """
        设置光电二极管传感器的测量带宽。
        name: 'HI' (高带宽) 或 'LO' (低带宽, 噪声更小)。
        """
        if name.upper() not in self.bw:
            raise ValueError("带宽名称必须是 'HI' 或 'LO'。")
        self.inst.write(f"INP:PDIO:FILT:LPAS:STAT {self.bw[name.upper()]}")
        self.bandwidth = name.upper()

    def getBandwidth(self):
        """返回当前的带宽设置 ('HI' 或 'LO')。"""
        state = self.inst.query("INP:PDIO:FILT:LPAS:STAT?").strip()
        return "HI" if state == "1" else "LO"

    def setAvgCount(self, count=10):
        """设置平均采样次数。"""
        self.inst.write(f"SENS:AVER:COUN {int(count)}")
        self.avg_count = int(count)

    def getAvgCount(self):
        """返回当前的平均采样次数。"""
        return int(self.inst.query("SENS:AVER:COUN?"))

    def setRangeAuto(self, auto_on=True):
        """设置功率测量是否为自动量程。"""
        state = "ON" if auto_on else "OFF"
        self.inst.write(f"POW:RANG:AUTO {state}")

    def getRangeAuto(self):
        """返回自动量程是否开启 (True/False)。"""
        state = self.inst.query("POW:RANG:AUTO?").strip()
        return state == "1"

    def getPower(self):
        """获取一次功率测量值，单位为瓦特 (W)。"""
        return float(self.inst.query("MEAS:POW?"))
        
    def getSensorInfo(self):
        """获取当前连接的传感器的信息。"""
        info_str = self.inst.query("SYST:SENS:IDN?").strip()
        parts = info_str.split(',')
        return {
            'name': parts[0],
            'serial_number': parts[1],
            'calibration_message': parts[2],
            'type': parts[3],
            'subtype': parts[4],
            'flags': parts[5]
        }
        
    def zero(self):
        """执行一次清零/背景校准。请确保在执行前遮挡传感器。"""
        print("正在执行清零操作，请稍候...")
        # 清零命令会阻塞直到完成，可能需要增加超时时间
        default_timeout = self.inst.timeout
        self.inst.timeout = 10000 # 临时增加超时到 10 秒
        try:
            self.inst.write("SENS:CORR:COLL:ZERO:INIT")
            # 在某些 VISA 实现中，可能需要等待操作完成
            # 使用 *OPC? 查询操作是否完成
            self.inst.query("*OPC?") 
            print("清零完成。")
        finally:
            self.inst.timeout = default_timeout # 恢复原始超时

    def write(self, message, q=False):
        """
        底层的写/查询封装。
        如果 q=True，则执行 query 操作，否则执行 write 操作。
        """
        if q:
            return self.inst.query(str(message))
        else:
            self.inst.write(str(message))

    def close(self):
        """关闭与仪器的连接。"""
        self.inst.close()
        print("PM100D 连接已关闭。")
