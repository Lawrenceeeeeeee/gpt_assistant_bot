import pandas as pd
import torch
from torch import nn
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader, TensorDataset

# 确保CUDA是否可用
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# 加载测试数据集
# 假设数据集为 CSV 格式，路径替换为你的数据集路径
# 数据集应包含列：'ts', 'o', 'h', 'l', 'c', 'v'，分别为时间戳、开盘、最高、最低、收盘和成交量
df_test = pd.read_csv('predictions\\Datas\\btc_usdt_swap_1h_10000.csv')

# 计算比值
df_test['o_ratio'] = df_test['o'].pct_change()
df_test['h_ratio'] = df_test['h'].pct_change()
df_test['l_ratio'] = df_test['l'].pct_change()
df_test['c_ratio'] = df_test['c'].pct_change()

# 标准化 v 列到 0-0.1 范围
scaler = MinMaxScaler(feature_range=(0, 0.1))
df_test['v_scaled'] = scaler.fit_transform(df_test[['v']])

# 去除空值（第一个时间点没有比值，因为计算了 pct_change）
df_test = df_test.dropna()

# 提取自变量（o_ratio, h_ratio, l_ratio, v_scaled）和目标变量（c_ratio）
X_test = df_test[['o_ratio', 'h_ratio', 'l_ratio', 'v_scaled']].values
y_test = df_test['c_ratio'].values

# 转换为 PyTorch Tensor
X_test_tensor = torch.tensor(X_test, dtype=torch.float32).to(device)
y_test_tensor = torch.tensor(y_test, dtype=torch.float32).to(device)

# 创建测试集的数据加载器
test_dataset = TensorDataset(X_test_tensor, y_test_tensor)
test_loader = DataLoader(test_dataset, batch_size=2, shuffle=False)

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

# 设置模型参数（与训练时一致）
input_size = 4  # 对应于 o_ratio, h_ratio, l_ratio, v_scaled
num_heads = 2
hidden_dim = 128
num_layers = 2
output_size = 1  # 预测目标为 c_ratio

# 初始化模型并加载已训练的权重
model = TransformerModel(input_size, num_heads, hidden_dim, num_layers, output_size).to(device)
model.load_state_dict(torch.load('predictions\\Models\\transformer_model.pth'))
model.eval()

# 执行回测
predictions = []
actuals = []

with torch.no_grad():
    for batch_X, batch_y in test_loader:
        output = model(batch_X.unsqueeze(1))  # 调整输入数据的形状
        if output.dim() > 1:
            predictions.extend(output.squeeze(1).cpu().numpy())
        else:
            predictions.append(output.cpu().item())
        actuals.extend(batch_y.cpu().numpy())

# 将预测值和实际值保存为 CSV 文件
result_df = pd.DataFrame({
    'Actual': actuals,
    'Predicted': predictions
})
result_df.to_csv('backtest_results.csv', index=False)
print("回测结果已保存为 backtest_results.csv")

# 绘制实际值与预测值的对比图表
plt.figure(figsize=(10, 6))
plt.plot(actuals, label='Actual')
plt.plot(predictions, label='Predicted', linestyle='--')
plt.xlabel('Time Steps')
plt.ylabel('C Ratio')
plt.legend()
plt.title('Backtesting: Actual vs Predicted')
plt.show()
