import pandas as pd
import torch
from torch import nn
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader, TensorDataset

# 确保CUDA是否可用
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# 假设你已经将数据加载为 pandas DataFrame
# 你可以用如下代码加载数据 (示例CSV文件路径，替换为实际路径)
df = pd.read_csv('predictions\\Datas\\btc_usdt_swap_1h_10000.csv')

# 计算比值
df['o_ratio'] = df['o'].pct_change()
df['h_ratio'] = df['h'].pct_change()
df['l_ratio'] = df['l'].pct_change()
df['c_ratio'] = df['c'].pct_change()

# 标准化 v 列到 0-0.1
scaler = MinMaxScaler(feature_range=(0, 0.1))
df['v_scaled'] = scaler.fit_transform(df[['v']])

# 去除空值（第一行会是 NaN，因为计算了 pct_change）
df = df.dropna()

# 提取自变量（o_ratio, h_ratio, l_ratio, v_scaled）和目标变量（c_ratio）
X = df[['o_ratio', 'h_ratio', 'l_ratio', 'v_scaled']].values
y = df['c_ratio'].values

# 划分训练集和测试集
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# 转换为 PyTorch Tensor
X_train_tensor = torch.tensor(X_train, dtype=torch.float32).to(device)
y_train_tensor = torch.tensor(y_train, dtype=torch.float32).to(device)
X_test_tensor = torch.tensor(X_test, dtype=torch.float32).to(device)
y_test_tensor = torch.tensor(y_test, dtype=torch.float32).to(device)

# 创建数据集和数据加载器
train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
test_dataset = TensorDataset(X_test_tensor, y_test_tensor)

train_loader = DataLoader(train_dataset, batch_size=2, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=2, shuffle=False)

# 定义 Transformer 模型
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
        src = src.permute(1, 0, 2)  # 需要将序列长度放在第一维度 (seq_length, batch_size, input_size)
        output = self.transformer(src)
        output = output.permute(1, 0, 2)  # 还原维度
        output = self.fc(output[:, -1, :])  # 取最后一个时间步的输出
        return output

# 设置参数
input_size = 4  # 对应于 o_ratio, h_ratio, l_ratio, v_scaled
num_heads = 2
hidden_dim = 128
num_layers = 2
output_size = 1  # 预测目标为 c_ratio

# 初始化模型并移动到CUDA
model = TransformerModel(input_size, num_heads, hidden_dim, num_layers, output_size).to(device)

# 损失函数和优化器
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# 训练模型
epochs = 100
train_losses = []
test_losses = []

for epoch in range(epochs):
    model.train()
    total_train_loss = 0
    for batch_X, batch_y in train_loader:
        optimizer.zero_grad()
        output = model(batch_X.unsqueeze(1))  # 添加一个维度表示序列长度
        loss = criterion(output.squeeze(), batch_y)
        loss.backward()
        optimizer.step()
        total_train_loss += loss.item()

    # 记录训练集损失
    avg_train_loss = total_train_loss / len(train_loader)
    train_losses.append(avg_train_loss)

    # 在测试集上进行评估
    model.eval()
    total_test_loss = 0
    with torch.no_grad():
        for batch_X, batch_y in test_loader:
            output = model(batch_X.unsqueeze(1))
            loss = criterion(output.squeeze(), batch_y)
            total_test_loss += loss.item()

    # 记录测试集损失
    avg_test_loss = total_test_loss / len(test_loader)
    test_losses.append(avg_test_loss)

    print(f'Epoch {epoch+1}/{epochs}, Train Loss: {avg_train_loss}, Test Loss: {avg_test_loss}')

# 保存模型
torch.save(model.state_dict(), 'predictions\\Models\\transformer_model.pth')
print("模型已保存为 transformer_model.pth")

# 绘制训练和测试集的损失曲线
plt.figure(figsize=(10, 6))
plt.plot(train_losses, label='Train Loss')
plt.plot(test_losses, label='Test Loss')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.legend()
plt.title('Train and Test Loss over Epochs')
plt.show()

# 回测模型
model.eval()
predictions = []
actuals = []

with torch.no_grad():
    for batch_X, batch_y in test_loader:
        output = model(batch_X.unsqueeze(1))
        predictions.extend(output.squeeze().cpu().numpy())
        actuals.extend(batch_y.cpu().numpy())

# 绘制回测结果
plt.figure(figsize=(10, 6))
plt.plot(actuals, label='Actual')
plt.plot(predictions, label='Predicted', linestyle='--')
plt.xlabel('Time Steps')
plt.ylabel('C Ratio')
plt.legend()
plt.title('Backtesting: Actual vs Predicted')
plt.show()
