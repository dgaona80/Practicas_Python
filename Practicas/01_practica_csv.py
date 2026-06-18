import pandas as pd

"""
    1.- Contexto: soy una analista y estoy analizando un dataframe
    2.- Petición o pregunta: dale órdenes
    3.- limitantes: quiero .... pero que tenga....
    4.- Recordatorio, dale los puntos fuertes: recuerda el .... que te dije
    5.- Generar resultados esperados

"""

df = pd.read_csv("practicas\data\clientes.csv")

# ver tipos de datos

print(df.dtypes)

#1.2 valores nulos
print(df.isnull().sum())

#1.3 Duplicados
print(df.duplicated().sum())

#1.4 valores únicos por columna (inconsistencia)
print(df["Ciudad"].unique())
#print(df["pais"].unique())

#1.5 ver registros problemáticos
print(df[df["Edad"].apply(lambda x: isinstance(x, str))]) #edadd como texto

print(df["Gasto"].describe())