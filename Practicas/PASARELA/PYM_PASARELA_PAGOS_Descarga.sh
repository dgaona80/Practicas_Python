#!/bin/bash
source ~/.bashrc > /dev/null 2>&1
# Configurar el entorno (si es necesario)
export PATH=$PATH:/dwh/dwhprod/.local/bin
export PATH=$PATH:/usr/bin/python3.11

# *********************************************************************************************************
# Nombre shell:        PYM_PASARELA_PAGOS_Descarga.sh
# Descripcion corta:   Shell que ejecuta el programa PYM_PASARELA_PAGOS_Descarga.py
# Detalle del proceso: Shell que ejecuta el programa PYM_PASARELA_PAGOS_Descarga.py
# Realizado por:       XIDERAL(DDGL)
# Fecha Creacion:      06/09/2024
# Ruta del Shell DEV:	   /dwh/dwhdes/FILES/Programs/Shells/
# Ruta del Shell PROD:	   /dwh/dwhprod/FILES/Programs/Shells/
# *********************************************************************************************************  
# Control de versiones: 
# Modificacion:      
# Realizado por:     
# Fecha Creacion:    
# *********************************************************************************************************  
# Este proceso genera la carga del di­a anterior
echo "---------------------------------------------"
echo "INCIO DE EJECUCION : "`date +"%Y/%m/%d %H:%M:%S"`
echo "PROCESO        : PYM_PASARELA_PAGOS_Descarga.py"
echo "---------------------------------------------"
  
python3 /dwh/dwhprod/FILES/Programs/Shells/PYM_PASARELA_PAGOS_Descarga.py

echo "---------------------------------------------"
echo "FIN DE EJECUCION : "`date +"%Y/%m/%d %H:%M:%S"`
echo "---------------------------------------------"
#Opcion de reproceso quitar el comentario y capturar la fecha en el formato indicado YYYYMMDD:
#python3 /dwh/dwhprod/FILES/Programs/Shells/PYM_PASARELA_PAGOS_Descarga.py YYYYMMDD