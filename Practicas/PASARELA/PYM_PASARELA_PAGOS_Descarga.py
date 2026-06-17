#!/usr/bin/env python
# coding: utf-8

# ## PROCESO DE CARGA: PASARELA PAGOS

# In[9]:


# ---------------------------PROCESO DE CARGA PASARELA PAGOS----------------------------------
# V 1.0
# Última edición: 06 Agosto 2024
# lectura de parámetros el S3 por medio del archivo: archivo: config.ini
# Librerías requeridas -> boto3 |  oracledb | datetime | configparser | csv 
# pip install boto3

import boto3
import configparser
import os
import oracledb
import csv
import sys
from pyathena import connect
from datetime import datetime, timedelta

#--------------------------Bloque 1: cargar la configuración desde el archivo config.ini

def load_config():
    config = configparser.ConfigParser()
    config.read('/dwh/dwhprod/FILES/Programs/Configuration/config.ini')
    return config['aws'] # traemos lo que tiene
     
#----------------------------Bloque 2: definición de funciones-----------------------------------

# Función para obtener la fecha de ayer o usar una proporcionada
def get_date_or_yesterday(date_str=None):
    if date_str:
        return datetime.strptime(date_str, '%Y%m%d')
    else:
        return datetime.now() - timedelta(1)


# función para obtener el archivo, ingresa la fecha manual o por sistema
def get_file_s3(date_to_use):

    # obtener los valores del archivo .ini
    config = load_config()
    s3_staging_dir = config.get('s3_staging_dir')
    s3_region = config.get('s3_region')
    folder_path = config.get('folder_path')
    aws_profile = config.get('aws_profile', 'payment')
    download_path = config.get('download_path')

    if not s3_staging_dir or not s3_region or not folder_path or not download_path:
         raise ValueError("Configuracion incompleta en 'config.ini'")

    if aws_profile:
        os.environ['AWS_PROFILE'] = aws_profile

    try:
        
        conn = connect(
            s3_staging_dir=s3_staging_dir,
            region_name=s3_region
        )
        print("Conexion a S3 establecida con exito.")
    
        # Formatear la fecha para el nombre del archivo
        formatted_date = date_to_use.strftime('%Y%m%d')
        print(f'Se obtendrá el archivo CVS de la fecha: {formatted_date}')   
        # Formatear la ruta de la carpeta en S3 con el mes y año corriente
        folder_path_s3 = os.path.join(folder_path, date_to_use.strftime('%Y/%m/'))
        # Nombre del archivo a descargar        
        file_name = f'MTT_Pagos{formatted_date}.csv'
        download_path_d=os.path.join(download_path,formatted_date)
        print(f'Carpeta S3: {folder_path_s3}')

        if not os.path.exists(download_path_d):
            print(f'La carpeta local {formatted_date} no existe, se va a crear')
            os.makedirs(download_path_d)
            print(f'Carpeta {formatted_date} creada.')
        
        # Crear un cliente S3 usando boto3 y las credenciales del archivo de configuración
        s3 = boto3.client('s3') 

        # Descargar el archivo de S3
        try:
            s3.download_file(s3_staging_dir, os.path.join(folder_path_s3, file_name), os.path.join(download_path_d, file_name))
            print(f'Archivo {file_name} descargado exitosamente en {download_path_d}.')
            return file_name,download_path_d
    
        except Exception as e:
            print(f'Error al descargar el archivo: {e}')
            raise 
    except Exception as e:
        print(f"Error al intentar conectarse a S3: {e}")
        raise
    
def load_config_dwh():
    # Cargar configuración desde variables de entorno
    return {
        'DWH_USER': os.getenv('DWH_USER'),
        'DWH_PASSWORD': os.getenv('DWH_PASSWORD'),
        'DWH_HOST': os.getenv('DWH_HOST'),
        'DWH_PORT': os.getenv('DWH_PORT'),
        'DWH_SID': os.getenv('DWH_SID')
    }


def loader_dwh(date_to_use,file_name,download_path_d):
    
    #----------------------conexión general a la BD
    config = load_config_dwh()
    #print(config)
    user = config.get('DWH_USER')
    password = config.get('DWH_PASSWORD')
    host = config.get('DWH_HOST')
    port = config.get('DWH_PORT')
    sid = config.get('DWH_SID')
    #print(config)

    if not all([user, password, host, port, sid]):
        raise ValueError("Faltan variables de entorno necesarias para la conexion.")

    dsn = f"{host}:{port}/{sid}"
    
    
    formatted_date = date_to_use.strftime('%Y%m%d')
    

    #-----Módulo para validar si existe información en la tabla
    try:
        connection = oracledb.connect(user=user, password=password, dsn=dsn)
        cursor_count_data=connection.cursor()
        cve_dia_delete=int(date_to_use.strftime('%Y%m%d'))
        cursor_count_data.execute("SELECT COUNT(1) FROM STG_PA_SAT.PYM_PASARELA_PAGOS_DIGITAL WHERE CVE_DIA = :dia", dia = cve_dia_delete)

        #Obtener el número de registros:
        count_data = cursor_count_data.fetchone()[0] 
        print('')
        print(f' Existen {count_data}  registros para la fecha: {date_to_use}')
        
    except oracledb.Error as error:
        print(f'Error con la conexión de ORACLE: {error}')

    except Exception as err_other:
        print(f'Error en el proceso: {err_other}')

    finally:
        if cursor_count_data:
            cursor_count_data.close()

    #-----Módulo para borrar información existente
    if count_data > 0:
        try:
            cursor_del_data=connection.cursor()
            cursor_del_data.execute("DELETE FROM STG_PA_SAT.PYM_PASARELA_PAGOS_DIGITAL WHERE CVE_DIA = :dia", dia = cve_dia_delete)
            print(f' {count_data} registros borrados, se realizará reproceso.')

            #aplicar los cambios
            connection.commit()

        except oracledb.DatabaseError as error:
            print(f'Error con la conexión de ORACLE: {error}')

        except Exception as err_other:
            print(f'Error en el proceso: {err_other}')
    
        finally:
            if cursor_del_data:
                cursor_del_data.close()
            else:
                print(f'Inicio de carga de datos para la fecha:{date_to_use}')
        
    
    #-----Módulo para insertar la información del archivo 
    try:
        cursor = connection.cursor()
        #creación de variables para contar registros y validar existencia de particiones
        cve_dia = int(date_to_use.strftime('%Y%m%d'))
        cve_mes = int(date_to_use.strftime('%Y%m'))
        num_particion = int(date_to_use.strftime('%Y%m%d'))
        particion = f'PART_{num_particion}'


        try:
            cursor_existe_particion=connection.cursor()
            sql = f'SELECT COUNT(1) FROM ALL_TAB_PARTITIONS WHERE TABLE_NAME = \'PYM_PASARELA_PAGOS_DIGITAL\' AND PARTITION_NAME = \'{particion}\''
            cursor_existe_particion.execute(sql)

            bandera_particion = cursor_existe_particion.fetchone()[0] 
            cursor_existe_particion.close()
       
            if bandera_particion == 0:
                print(f'No existe la partición {particion}, se va a crear.')
                cursor_particion=connection.cursor()
                sql = f'ALTER TABLE STG_PA_SAT.PYM_PASARELA_PAGOS_DIGITAL ADD PARTITION {particion} VALUES LESS THAN ({num_particion+1}) TABLESPACE PA_STG_SAT_DATA_01'
                cursor_particion.execute(sql)
                if cursor_particion:
                    #applicar los cambios
                    connection.commit()
                    print(f'Partición creada.')
                    cursor_particion.close()
            else:
                print(f'Partición {particion} existente...')

        except oracledb.Error as error:
            print(f'Error con la conexión de ORACLE: {error}')

        except Exception as err_other:
            print(f'Error en el proceso: {err_other}')
    
          
        with open(os.path.join(download_path_d, file_name),"r", encoding='utf-8') as csv_file:
            print(f'Inicio de lectura del archivo CSV e inserción en la tabla: PYM_PASARELA_PAGOS_DIGITAL')
            csv_reader = csv.DictReader(csv_file,delimiter=',')
            for lines in csv_reader:
                if len(lines['Payment Start Time']) >= 10:
                    lines['Payment Start Time']=datetime.strptime(lines['Payment Start Time'],'%Y-%m-%d %H:%M:%S').date()
                
                if len(lines['Payment End Time']) >= 10:
                    lines['Payment End Time']=datetime.strptime(lines['Payment End Time'],'%Y-%m-%d %H:%M:%S').date()
             
                if len(lines['Fulfillment Start Time']) >= 10:
                    lines['Fulfillment Start Time']=datetime.strptime(lines['Fulfillment Start Time'],'%Y-%m-%d %H:%M:%S').date()
                  
                if len(lines['Fulfillment End Time']) >= 10:
                    lines['Fulfillment End Time']=datetime.strptime(lines['Fulfillment End Time'],'%Y-%m-%d %H:%M:%S').date()
    
                if len(lines['Payment Callback Start Timestamp']) >= 10:
                    lines['Payment Callback Start Timestamp']=datetime.strptime(lines['Payment Callback Start Timestamp'],'%Y-%m-%d %H:%M:%S').date()
                
                if len(lines['Payment Callback End Timestamp']) >= 10:
                    lines['Payment Callback End Timestamp']=datetime.strptime(lines['Payment Callback End Timestamp'],'%Y-%m-%d %H:%M:%S').date()
                
                if len(lines['Fulfillment Callback Start Timestamp']) >= 10:
                    lines['Fulfillment Callback Start Timestamp']=datetime.strptime(lines['Fulfillment Callback Start Timestamp'],'%Y-%m-%d %H:%M:%S').date()
                
                if len(lines['Fulfillment Callback End Timestamp']) >= 10:
                    lines['Fulfillment Callback End Timestamp']=datetime.strptime(lines['Fulfillment Callback End Timestamp'],'%Y-%m-%d %H:%M:%S').date()

                if len(lines['Invoice Start Timestamp']) >= 10:
                    lines['Invoice Start Timestamp']=datetime.strptime(lines['Invoice Start Timestamp'],'%Y-%m-%d %H:%M:%S').date()
                    
                if len(lines['Invoice End Timestamp']) >= 10:
                    lines['Invoice End Timestamp']=datetime.strptime(lines['Invoice End Timestamp'],'%Y-%m-%d %H:%M:%S').date()
                
                if len(lines['Refund End TimeStamp']) >= 10:
                    lines['Refund End TimeStamp']=datetime.strptime(lines['Refund End TimeStamp'],'%Y-%m-%d %H:%M:%S').date()

                if len(lines['Local Payment Start Timestamp']) >= 10:
                    lines['Local Payment Start Timestamp']=datetime.strptime(lines['Local Payment Start Timestamp'],'%Y-%m-%d %H:%M:%S').date()
                
                cursor.execute(
                "insert into STG_PA_SAT.PYM_PASARELA_PAGOS_DIGITAL ( CVE_DIA, CVE_MES, TRANSACTION_ID, EXTERNALPAYMENTID, BATCHID, NAME, UUID, "
                "DEVICEID, EMAIL, APPLICATIONID, APPLICATIONBILLINGSYSTEMNAME, MERCHANTNAME, " 
                "MERCHANTNUMBER, HADEXTRAFRAUDPREVENTION, HADEXTRAVALIDATION, COUNTRY, ORDERID, " 
                "PURCHASEORDERID, BODY, ACCOUNTNUMBER, PRODUCTREFERENCE, ACCOUNTTYPE, ORDERSTATUS, "
                "PAYMENTPROCESSORTRANSACTIONID, CURRENCY, TOTALPURCHASEAMOUNT, CURRENTPAYMENTSTATUS, " 
                "FINALPAYMENTSTATUS, PAYMENTAPPROVED, TOKENIZED, PAYMENTSTARTTIME, PAYMENTENDTIME, "
                "PAYMENTAUTHORIZATIONCODE, PAYMENTREJECTREASON, PGERRORCODE, MASKEDPAYMENTTOKEN, "
                "MASKEDCREDITCARDNUMBER, EXPIRATIONMONTH, EXPIRATIONYEAR, PROCESSINGPARTNER, "
                "FINALFULFILLMENTSTATUS, CURRENTFULFILLMENTSTATUS, FULFILLMENTCONFIRMATIONCODE, "
                "FULFILLMENTSTARTTIME, FULFILLMENTENDTIME, FULFILLMENTREJECTREASON, FULFILLMENTSUCCEEDED, "
                "FULFILLMENTHTTPSTATUSCODE, PAY_CALL_STARTTIMESTAMP, PAY_CALL_ENDTIMESTAMP, PAY_CALL_STATUS, "
                "PAY_CALL_RESP_HTTPSTATUSCODE, PAY_CALL_RESP_ERRORCODE, PAY_CALL_RESP_ERRORDETAILS, FULF_CALL_STARTTIMESTAMP, "
                "FULF_CALL_ENDTIMESTAMP, FULF_CALL_STATUS, FULF_CALL_RESP_HTTPSTATUSCODE, FULF_CALL_RESP_ERRORCODE, "
                "FULF_CALL_RESP_ERRORDETAILS, INVOICESTARTTIMESTAMP, INVOICEENDTIMESTAMP, INVOICESTATUS, "
                "INVOICEHTTPSTATUSCODE, INVOICECONFIRMATIONCODE, INVOICERESPONSE, PAYMENTCHANNEL, PRODUCTTYPE, "
                "RECONCILIATIONID, REFUNDENDTIMESTAMP, REFUNDREJECTREASON, REFUNDREQUESTID, CARDTYPE, "
                "LOCALPAYMENTSTARTTIMESTAMP, AFS_REQUEST_ID, CUSTOMER_IP_ADDRESS ) "
    
                "values (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13, :14, :15, :16, :17, :18, :19, :20, "
                ":21, :22, :23, :24, :25, :26, :27, :28, :29, :30, :31, :32, :33, :34, :35, :36, :37, :38, :39, "
                ":40, :41, :42, :43, :44, :45, :46, :47, :48, :49, :50, :51, :52, :53, :54, :55, :56, :57, :58, "
                ":59, :60, :61, :62, :63, :64, :65, :66, :67, :68, :69, :70, :71, :72, :73, :74, :75, :76)" ,
                (cve_dia,cve_mes,lines['Transaction ID'], lines['External Payment ID'], lines['Batch ID'], lines['Name'].strip(), lines['UUID'], lines['Device ID'], lines['Email'], 
                lines['Application ID'], lines['Application/Billing System Name'], lines['Merchant Name'], lines['Merchant Number'], lines['Had Extra Fraud Prevention'], 
                lines['Had Extra Validation'], lines['Country'], lines['Order ID'], lines['Purchase Order ID'], lines['Body'], lines['Account Number'], lines['Product Reference'], 
                lines['Account Type'], lines['Order Status'], lines['Payment Processor Transaction ID'], lines['Currency'], lines['Total Purchase Amount'], lines['Current Payment Status'],
                lines['Final Payment Status'], lines['Payment Approved'], lines['Tokenized'], lines['Payment Start Time'], lines['Payment End Time'], lines['Payment Authorization Code'], 
                lines['Payment Reject Reason'], lines['PG Error Code'], lines['Masked Payment Token'], lines['Masked Credit Card Number'], lines['Expiration Month'], lines['Expiration Year'], 
                lines['Processing Partner'], lines['Final Fulfillment Status'], lines['Current Fulfillment Status'], lines['Fulfillment Confirmation Code'], lines['Fulfillment Start Time'],
                lines['Fulfillment End Time'], lines['Fulfillment Reject Reason'], lines['Fulfillment Succeeded'], lines['Fulfillment HTTP Status Code'], lines['Payment Callback Start Timestamp'], 
                lines['Payment Callback End Timestamp'], lines['Payment Callback Status'], lines['Payment Callback Response HTTP Status Code'], lines['Payment Callback Response Error Code'], 
                lines['Payment Callback Response Error Details'], lines['Fulfillment Callback Start Timestamp'], lines['Fulfillment Callback End Timestamp'], lines['Fulfillment Callback Status'],
                lines['Fulfillment Callback Response HTTP Status Code'], lines['Fulfillment Callback Response Error Code'], lines['Fulfillment Callback Response Error Details'], lines['Invoice Start Timestamp'],
                lines['Invoice End Timestamp'], lines['Invoice Status'], lines['Invoice HTTP Status Code'], lines['Invoice Confirmation Code'], lines['Invoice Response'], lines['Payment Channel'],
                lines['Product Type'], lines['Reconciliation Id'], lines['Refund End TimeStamp'], lines['Refund Reject Reason'], lines['Refund Request Id'], lines['Card Type'], lines['Local Payment Start Timestamp'],
                lines['AFS Request ID'], lines['Customer IP Address'])       
                )
            connection.commit()
            print(f'Información con la fecha: {date_to_use} cargada exitosamente...')        
          
    except oracledb.Error as error:
        print(f'Error con la conexión de ORACLE: {error}')

    except Exception as err:
        print(f'Error en el proceso: {err}')

    finally:
        if cursor:
            #Si no hay error, ejecuta commit
            cursor.close()
    
        if connection:
            connection.close()
    return;

print('')
print(f'--------------- Proceso Payment Gateway -------------------')
print(f'--------------------- S3 -> DWH ---------------------------')
print('')

argumentos = sys.argv

if len(argumentos) == 1:
    print(f'------------ Carga de información del día anterior --------')
    print('')
    date_to_use = get_date_or_yesterday()
    tupla_var=get_file_s3(date_to_use)
    file_name = tupla_var[0]
    download_path_d = tupla_var[1]
    loader_dwh(date_to_use,file_name,download_path_d)

if len(argumentos) == 2:
    print(f'------------------- Reproceso -----------------------------')
    print('')
    print('Reproceso')
    date_to_use = get_date_or_yesterday(argumentos[1]) 
    #invocar la función de obtención del archivo de S3 con la fecha generada (aquí no se realizan cambios)
    tupla_var = get_file_s3(date_to_use)
    file_name = tupla_var[0]
    download_path_d = tupla_var[1]
    loader_dwh(date_to_use,file_name,download_path_d) 

