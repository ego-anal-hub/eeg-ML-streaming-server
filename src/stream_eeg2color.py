from pyspark import SparkConf
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import *
from pyspark.sql.types import *
import json
import numpy as np
from scipy.fft import fft
import math
import warnings
import operator
# import pandas as pd

import findspark
findspark.init()

# 사용자 정의 함수 (FFT 처리)
def apply_fft(values):
    # return [int(v) for v in values.tolist()]

    # values = [item for sublist in values for item in sublist]
    spectrum = fft(values)
    # spectrum = [r for r in spectrum]

    # 주파수 대역 선택
    sampling_rate = 256  # 샘플링 주파수 (Hz)
    frequency_resolution = sampling_rate / len(values)  # 주파수 해상도

    domain_fband_data = {
        'delta' : {
            'power' : float,
            'range' : [0.5, 4], # 연수,뇌교,중뇌 / 무의식 / 깊은수면,내면의식,수면,무의식,기본활동,회복,재생 / RGB (0, 0, 100)
            'rgb_ratio' : (0, 0, 100)
        },
        'theta' : {
            'power' : float,
            'range' : [4, 8], # 구피질 / 내적의식 / 졸음,얕은수면,창의력,상상력,명상,꿈,감정,감성,예술적노력 / RGB (255, 215, 0)
            'rgb_ratio' : (255, 215, 0)
        },
        'slow-alpha' : {
            'power' : float,
            'range' : [8, 9], # 내적의식 / 명상,무념무상
            'rgb_ratio' : None
        },
        'middle-alpha' : {
            'power' : float,
            'range' : [10, 12], # 내적의식 / 지감,번득임,문제해결,스트레스해소,학습능률향상,기억력,집중력최대
            'rgb_ratio' : None
        },
        'smr' : {
            'power' : float,
            'range' : [12, 15], # 후방신피질 / 내적의식 / 각성,일학업능률최적,주의집중,약간의긴장,간단한집중,수동적두뇌활동
            'rgb_ratio' : None
        },
        'alpha' : {
            'power' : float,
            'range' : [8, 13], # 후두엽 / 내적의식 / 휴식,긴장해소,집중력향상,안정감,근육이완,눈뜬상태과도->과거미래환상 / RGB (0, 255, 255)
            'rgb_ratio' : (0, 255, 255)
        },
        'beta' : {
            'power' : float,
            'range' : [14, 30], # 눈감았을때측두엽,떴을때전두엽 / 외적의식 / 각성,인지활동,집중,의식적사고,육체활동,몰두,복잡한업무 / RGB (255, 192, 203)
            'rgb_ratio' : (255, 192, 203)
        },
        'high-beta' : {
            'power' : float,
            'range' : [18, 30], # 외적의식 / 불안,긴장,경직
            'rgb_ratio' : None
        },
        'gamma' : {
            'power' : float,
            'range' : [30, 100], # 전두엽,두정엽 / 외적의식 / 문제해결흥분,고급인지기능,불안,순간인지,능동적복합정신기능 / RGB (128, 0, 128)
            'rgb_ratio' : (128, 0, 128)
        }
    }
    
    def process_color():
        def weighted_average(coordinates, weights):
            # Ignore the ComplexWarning for specific code blocks
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=np.ComplexWarning)
            weighted_sum = [np.sum(np.fromiter((cdn[i] * weight for cdn, weight in zip(coordinates, weights)), dtype=float)) for i in range(len(coordinates[0]))]
            total_weight = np.sum(np.fromiter(weights, dtype='float'))
            # weighted_avg = [cdn_sum / total_weight for cdn_sum in weighted_sum]
            weighted_avg = [cdn_sum / total_weight if total_weight != 0 else 0 for cdn_sum in weighted_sum]
            return weighted_avg

        # 예시 좌표와 가중치
        coordinates = [info['rgb_ratio'] for info in domain_fband_data.values() if info['rgb_ratio']]
        weights = [info['power'] for info in domain_fband_data.values() if info['rgb_ratio']]

        # 가중 평균 계산
        avg_color = weighted_average(coordinates, weights)
        return avg_color 

    # beta파에 해당하는 주파수 대역 선택
    for domain, info in domain_fband_data.items():
        domain_range = np.arange(int(info['range'][0] / frequency_resolution), int(info['range'][1] / frequency_resolution) + 1)
        domain_spectrum = spectrum[domain_range]
        min_power = np.min(domain_spectrum)
        max_power = np.max(domain_spectrum)
        domain_spectrum = [(power - min_power) / (max_power - np.min(domain_spectrum)) for power in domain_spectrum]
        domain_fband_data[domain]['power'] = np.mean(domain_spectrum)
        # domain_fband_data[domain]['power'] = np.sum(np.abs(domain_spectrum)).tolist()

    avg_color = process_color()
    result = [0,0,0]
    if any(math.isnan(x) for x in avg_color): result = [0,0,0]
    else: result = [int(v) for v in avg_color]

    # return avg_color
    return result

# 사용자 정의 함수로 변환
udf_apply_fft = udf(apply_fft, ArrayType(IntegerType()))

# SparkSession 생성
# spark = SparkSession.builder \
#     .appName("EEG-Analysis-SparkStreaming") \
#     .master("local[*]") \
#     .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0") \
#     .config("spark.sql.shuffle.partitions", "4") \
#     .config("spark.sql.streaming.statefulOperator.checkCorrectness.enabled", "false") \
#     .conf.set("spark.sql.execution.arrow.enabled", "true") \
#     .getOrCreate()

conf = SparkConf()
conf.set("spark.app.name", "EEG-Analysis-SparkStreaming")
conf.set("spark.master", "local[*]")
conf.set("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0")
conf.set("spark.sql.shuffle.partitions", "4")
conf.set("spark.sql.streaming.statefulOperator.checkCorrectness.enabled", "false")
conf.set("spark.sql.execution.arrow.enabled", "true")
# conf.set("spark.driver.memory", "2g")  # Increase this as needed
# conf.set("spark.executor.memory", "2g")  # Increase this as needed

spark = SparkSession.builder.config(conf=conf).getOrCreate()

# Kafka에서 스트림 데이터 읽기
kafka_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka_ip:9092") \
    .option("subscribe", "raw-eeg") \
    .option('client_id', 'eeg-da-server-consumer-1') \
    .option('group_id', 'da-group') \
    .load() \
    .selectExpr("CAST(value AS STRING)")

eeg_schema = StructType([
    StructField("time", StringType(), nullable=False),
    StructField("space", StructType([
        StructField("id", StringType(), nullable=False)
    ]), nullable=False),
    StructField("person", StructType([
        StructField("id", StringType(), nullable=False),
        StructField("eeg", StructType([
            StructField("ch1", StructType([
                StructField("pos", StringType(), nullable=False),
                StructField("value", FloatType(), nullable=False)
            ]), nullable=False),
            StructField("ch2", StructType([
                StructField("pos", StringType(), nullable=False),
                StructField("value", FloatType(), nullable=False)
            ]), nullable=False),
            StructField("ch3", StructType([
                StructField("pos", StringType(), nullable=False),
                StructField("value", FloatType(), nullable=False)
            ]), nullable=False),
            StructField("ch4", StructType([
                StructField("pos", StringType(), nullable=False),
                StructField("value", FloatType(), nullable=False)
            ]), nullable=False)
        ]), nullable=False)
    ]), nullable=False)
])

eeg_data = kafka_df.select(from_json(regexp_replace(col("value"), '\\\\|(^")|("$)', ''), eeg_schema).alias("eeg_data")) \
    .select(
        col("eeg_data.time").alias("time"),
        col("eeg_data.space.id").alias("spaceId"),
        col("eeg_data.person.id").alias("personalId"),
        col("eeg_data.person.eeg.ch1.value").alias("ch1_value"),
        col("eeg_data.person.eeg.ch2.value").alias("ch2_value"),
        col("eeg_data.person.eeg.ch3.value").alias("ch3_value"),
        col("eeg_data.person.eeg.ch4.value").alias("ch4_value")
    )

# 타임스탬프를 Spark의 'timestamp' 형식으로 변환
eeg_data = eeg_data.withColumn("time", 
                   expr("concat(substr(time, 1, 4), '-', substr(time, 5, 2), '-', substr(time, 7, 2), ' ', substr(time, 9, 2), ':', substr(time, 11, 2), ':', substr(time, 13, 2), '.', substr(time, 15, 3))"))
eeg_data = eeg_data.withColumn("time", to_timestamp(col("time"), "yyyy-MM-dd HH:mm:ss.SSS"))

# eeg_data = eeg_data.withWatermark(
#     "time", 
#     "2 seconds"
# )

# 윈도우 슬라이딩 처리를 위한 설정
# window_duration = "10 seconds"
# slide_duration = "1 seconds"
window_duration = "2 seconds"
slide_duration = "1.5 seconds"
# .withWatermark("time", "1 minutes")
eeg_data_windowed = eeg_data.withWatermark("time", "1 microseconds").withColumn(
    "window",
    window(col("time"), window_duration, slide_duration)
).groupBy(
    "window", "spaceId", "personalId"
).agg(
    udf_apply_fft(collect_list(col("ch1_value"))).alias("ch1_color"),
    udf_apply_fft(collect_list(col("ch2_value"))).alias("ch2_color"),
    udf_apply_fft(collect_list(col("ch3_value"))).alias("ch3_color"),
    udf_apply_fft(collect_list(col("ch4_value"))).alias("ch4_color"),
)
# .withWatermark("window", "10 seconds")

# eeg_data_windowed = eeg_data_windowed.withWatermark(
#     "window", 
#     "10 minutes"
# )

result_data = eeg_data_windowed.select(
    date_format(col("window.end"), "yyyyMMddHHmmssSSS").alias("time"),
    # col("window").alias("timestamp"),
    struct(
        col("spaceId").alias("id")
    ).alias("space"),
    struct(
        col("personalId").alias("id"),
        struct(
            struct(lit("TP9").alias("pos"), col("ch1_color")[0].alias("r"), col("ch1_color")[1].alias("g"), col("ch1_color")[2].alias("b")).alias("ch1"),
            struct(lit("AF7").alias("pos"), col("ch2_color")[0].alias("r"), col("ch2_color")[1].alias("g"), col("ch2_color")[2].alias("b")).alias("ch2"),
            struct(lit("AF8").alias("pos"), col("ch3_color")[0].alias("r"), col("ch3_color")[1].alias("g"), col("ch3_color")[2].alias("b")).alias("ch3"),
            struct(lit("TP10").alias("pos"), col("ch4_color")[0].alias("r"), col("ch4_color")[1].alias("g"), col("ch4_color")[2].alias("b")).alias("ch4")
        ).alias("color")
    ).alias("person")
)

# result_data = result_data.withWatermark(
#     "timestamp", 
#     "1 minutes"
# )


# JSON 변환
result_data_json = result_data.select(to_json(struct(col("*"))).alias("value"))

# Kafka로 내보내기
query = result_data_json \
    .writeStream \
    .outputMode("append") \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka_ip:9092") \
    .option("topic", "color-spectrum") \
    .option("client_id", 'eeg-da-server-producer-1') \
    .option("checkpointLocation", "C:/Users/cshiz/spark/spark-3.4.0-bin-hadoop3/checkpoint_1") \
    .start()

# query = result_data_json \
#     .writeStream \
#     .outputMode("append") \
#     .format("console") \
#     .option("truncate", "false") \
#     .start()

query.awaitTermination()