from stock_analyzer import StockAnalyzer

def main():
    # 输入参数
    stock_code = "002747"       # 股票代码
    start_date = "2025-05-01"   # 起始日期
    data_path = None            # 可以传入一个路径，例如 "./data/002747.csv"，也可以留空

    # 创建分析器对象
    analyzer = StockAnalyzer(stock_code=stock_code,
                             start_date=start_date,
                             data_path=data_path)

    # 执行分析
    df = analyzer.run()

    # 打印最后 5 条结果
    print(df.tail(5))

if __name__ == "__main__":
    main()

