# 发财

---

## 目录结构

strategy: 量化策略

update: 数据更新

note: 炒股笔记

utils: 全局依赖的配置和工具

vendor: 对开源adata项目文件的修改

---

## 使用示例

更新股票: python3 -m update.update_all_stocks -f local

预测股票: python3 -m strategy.predict -m fish_tub -b 1+4+5 -o predict_buy -c all
