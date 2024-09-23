import pandas as pd
import torch
from torch import nn
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt

# 确保CUDA是否可用
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# 定义 Transformer 模型（确保与训练时的模型一致）
class TransformerModel(nn.Module):
    def __init__(self, input_size, num_heads, hidden_dim, num_layers, output_size):
        super(TransformerModel, self).__init__()
        self.transformer_layer = nn.TransformerEncoderLayer(
            d_model=input_size, nhead=num_heads, dim_feedforward=hidden_dim
        )
        self.transformer = nn.TransformerEncoder(self.transformer_layer, num_layers=num_layers)
        self.fc = nn.Linear(input_size, output_size)

    def forward(self, src):
        # src shape: (batch_size, seq_length, input_size)
        src = src.permute(1, 0, 2)  # 调整维度顺序
        output = self.transformer(src)
        output = output.permute(1, 0, 2)  # 还原维度
        output = self.fc(output[:, -1, :])  # 只取最后一个时间步的输出
        return output

# 设置模型参数
input_size = 4  # 对应于 o_ratio, h_ratio, l_ratio, v_scaled
num_heads = 2
hidden_dim = 128
num_layers = 2
output_size = 1  # 预测目标为 c_ratio

# 初始化模型并加载已训练的权重
model = TransformerModel(input_size, num_heads, hidden_dim, num_layers, output_size).to(device)
model.load_state_dict(torch.load('Models/transformer_model.pth', map_location=torch.device('cpu')))
model.eval()

def predict_next_value(df):
    """
    接受包含最近时间段的数据，预测下一个时间点的值
    """

    # 计算比值
    df['o_ratio'] = df['o'].pct_change()
    df['h_ratio'] = df['h'].pct_change()
    df['l_ratio'] = df['l'].pct_change()
    df['c_ratio'] = df['c'].pct_change()

    # 标准化 v 列到 0-0.1 范围
    scaler = MinMaxScaler(feature_range=(0, 0.1))
    df['v_scaled'] = scaler.fit_transform(df[['v']])

    # 去除空值，只保留最新的一行
    df = df.dropna().tail(1)

    # 提取自变量
    X_input = df[['o_ratio', 'h_ratio', 'l_ratio', 'v_scaled']].values

    # 转换为 PyTorch Tensor
    X_input_tensor = torch.tensor(X_input, dtype=torch.float32).to(device)

    # 执行单步预测
    with torch.no_grad():
        # 扩展维度为 (1, 1, input_size) 以符合 Transformer 输入
        X_input_tensor = X_input_tensor.unsqueeze(0)
        output = model(X_input_tensor)

    # 预测值
    predicted_value = output.item()

    return predicted_value

if __name__ == '__main__':
    # 使用示例：传入 df，获取下一个时间点的预测值
    df_test = pd.read_csv('btc_usdt_swap_1h_10000.csv')
    next_prediction = predict_next_value(df_test)

    # 打印预测值
    print(f"Next predicted C Ratio: {next_prediction}")