
import streamlit as st
import pyodbc
import pandas as pd
import datetime

# Conexión a SQL Server
conn = pyodbc.connect(
    'DRIVER={SQL Server};SERVER=DESKTOP-7LU82GC;DATABASE=InventarioFarmacia;Trusted_Connection=yes;'
)
cursor = conn.cursor()

st.set_page_config(page_title="Inventario Farmacia", layout="wide")
st.markdown("<h1 style='color:#4CAF50; text-align:center;'>📦 Sistema de Inventario - Farmacia</h1>", unsafe_allow_html=True)

menu = st.sidebar.selectbox("Menú", [
    "Inventario General", 
    "Registrar Nuevo Lote", 
    "Registrar Movimiento (Ingreso/Salida)", 
    "Registrar Nuevo Insumo",
    "Movimientos Realizados"
])

# MÓDULO 1: INVENTARIO GENERAL
if menu == "Inventario General":
    st.subheader("📋 Inventario General")
    cursor.execute("""
        SELECT I.Cod_inv, P.Producto, P.Tipo, P.DCI, P.Laboratorio, I.Lote, I.Fecha_Vencimiento, I.Stock_unidad
        FROM INVENTARIO I
        JOIN INSUMOS P ON I.Cod_ins = P.Cod_ins
        ORDER BY I.Fecha_Vencimiento ASC
    """)
    data = cursor.fetchall()
    if data:
        df = pd.DataFrame([{
            "Código Inventario": row.Cod_inv,
            "Producto": row.Producto,
            "Tipo": row.Tipo,
            "DCI": row.DCI,
            "Laboratorio": row.Laboratorio,
            "Lote": row.Lote,
            "Fecha Vencimiento": row.Fecha_Vencimiento,
            "Stock (Unidades)": row.Stock_unidad
        } for row in data])
        st.dataframe(df, use_container_width=True, height=600)
    else:
        st.info("No hay inventario registrado.")

# MÓDULO 2: REGISTRO DE NUEVO LOTE
elif menu == "Registrar Nuevo Lote":
    st.subheader("➕ Registro de Nuevo Lote")

    cursor.execute("SELECT Cod_ins, Producto FROM INSUMOS")
    insumos = cursor.fetchall()
    insumo_dict = {f"{row.Producto} (ID: {row.Cod_ins})": row.Cod_ins for row in insumos}
    
    if insumo_dict:
        selected = st.selectbox("Seleccione un insumo", list(insumo_dict.keys()))
        cod_ins = insumo_dict[selected]
        lote = st.text_input("Lote")
        fecha_venc = st.date_input("Fecha de Vencimiento")
        cantidad = st.number_input("Cantidad ingresada (unidades)", min_value=1, step=1)

        if st.button("Registrar Lote"):
            # Verificar si ya existe el lote
            cursor.execute("""
                SELECT Cod_inv FROM INVENTARIO
                WHERE Cod_ins = ? AND Lote = ?
            """, (cod_ins, lote))
            resultado = cursor.fetchone()

            now = datetime.datetime.now()
            fecha = now.strftime('%Y-%m-%d')
            hora = now.strftime('%H:%M:%S')

            if resultado:
                cod_inv = resultado[0]
        
                # Actualiza el stock del lote existente
                cursor.execute("""
                    UPDATE INVENTARIO
                    SET Stock_unidad = Stock_unidad + ?
                    WHERE Cod_inv = ?
                """, (cantidad, cod_inv))

                # Registra la operación de ingreso
                cursor.execute("""
                    INSERT INTO OPERACION (Cod_inv, Tipo_Operacion, Cantidad, Fecha, Hora, Motivo)
                    VALUES (?, 'Ingreso', ?, ?, ?, 'Abastecimiento')
                """, (cod_inv, cantidad, fecha, hora))
        
                conn.commit()
                st.success("🔁 Lote ya existente: Stock actualizado correctamente.")
            else:
                # Inserta nuevo lote
                cursor.execute("""
                    INSERT INTO INVENTARIO (Cod_ins, Lote, Fecha_Vencimiento, Stock_unidad)
                    OUTPUT INSERTED.Cod_inv
                    VALUES (?, ?, ?, ?)
                """, (cod_ins, lote, fecha_venc.strftime('%Y-%m-%d'), cantidad))
        
                cod_inv = cursor.fetchone()[0]

                # Registra la operación
                cursor.execute("""
                    INSERT INTO OPERACION (Cod_inv, Tipo_Operacion, Cantidad, Fecha, Hora, Motivo)
                    VALUES (?, 'Ingreso', ?, ?, ?, 'Abastecimiento')
                """, (cod_inv, cantidad, fecha, hora))
        
                conn.commit()
                st.success("✅ Nuevo lote registrado correctamente.")
    else:
        st.warning("Debe registrar primero al menos un insumo.")

# MÓDULO 3: REGISTRO DE MOVIMIENTOS
elif menu == "Registrar Movimiento (Ingreso/Salida)":
    st.subheader("🔁 Registrar Movimiento de Insumos")

    cursor.execute("""
        SELECT I.Cod_inv, P.Producto, I.Lote, I.Fecha_Vencimiento
        FROM INVENTARIO I
        JOIN INSUMOS P ON I.Cod_ins = P.Cod_ins
        WHERE I.Stock_unidad > 0
    """)
    lotes = cursor.fetchall()
    lote_dict = {f"{row.Producto} - Lote {row.Lote} (Vence {row.Fecha_Vencimiento})": row.Cod_inv for row in lotes}

    if lote_dict:
        selected = st.selectbox("Seleccione un lote de insumo", list(lote_dict.keys()))
        cod_inv = lote_dict[selected]
        tipo = st.selectbox("Tipo de Operación", ["Ingreso", "Salida"])
        motivo_op = st.selectbox("Motivo", ["Retorno", "Abastecimiento"] if tipo == "Ingreso" else ["Asignación", "Vencimiento"])
        cantidad = st.number_input("Cantidad (unidades)", min_value=1, step=1)
        now = datetime.datetime.now()

        if st.button("Registrar Movimiento"):
            # Consultar stock actual
            cursor.execute("SELECT Stock_unidad FROM INVENTARIO WHERE Cod_inv = ?", (cod_inv,))
            stock_actual = cursor.fetchone().Stock_unidad

            if tipo == "Salida" and cantidad > stock_actual:
                st.error(f"❌ No se puede retirar más unidades ({cantidad}) que las disponibles ({stock_actual}).")
            else:
                now = datetime.datetime.now()
                fecha = now.strftime('%Y-%m-%d')
                hora = now.strftime('%H:%M:%S')

                # Registrar movimiento
                cursor.execute("""
                    INSERT INTO OPERACION (Cod_inv, Tipo_Operacion, Cantidad, Fecha, Hora, Motivo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cod_inv, tipo, cantidad, fecha, hora, motivo_op))

                # Actualizar inventario
                signo = 1 if tipo == "Ingreso" else -1
                cursor.execute("""
                    UPDATE INVENTARIO SET Stock_unidad = Stock_unidad + ? WHERE Cod_inv = ?
                """, (signo * cantidad, cod_inv))

                conn.commit()
                st.success(f"✅ Movimiento de tipo '{tipo}' registrado correctamente.")
    else:
        st.info("No hay lotes disponibles para registrar movimientos.")

# MÓDULO 4: REGISTRAR NUEVO INSUMO
elif menu == "Registrar Nuevo Insumo":
    st.subheader("🧾 Registro de Nuevo Insumo")

    with st.form("form_insumo"):
        producto = st.text_input("Nombre del Producto")
        tipo = st.selectbox("Tipo", ["Medicamento", "Insumo"])
        dci = st.text_input("DCI")
        gtin = st.text_input("GTIN")
        forma = st.text_input("Forma Farmacéutica")
        lab = st.text_input("Laboratorio")
        uso = st.selectbox("Uso", ["Agudo", "Curación de heridas", "Hospitalario"])
        submitted = st.form_submit_button("Registrar")

        if submitted:
            cursor.execute("SELECT ISNULL(MAX(Cod_ins), 0) + 1 FROM INSUMOS")
            nuevo_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO INSUMOS (Cod_ins, Producto, Tipo, DCI, GTIN, Forma_Farmac, Laboratorio, Uso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, nuevo_id, producto, tipo, dci, gtin, forma, lab, uso)
            conn.commit()
            st.success("✅ Insumo registrado correctamente.")


# MÓDULO 5: MOVIMIENTOS

elif menu == "Movimientos Realizados":
    st.subheader("📦 Historial de Movimientos")

    cursor.execute("""
        SELECT 
            O.cod_ope,
            P.Producto,
            I.Lote,
            O.Tipo_Operacion,
            O.Cantidad,
            O.Fecha,
            O.Hora,
            O.Motivo
        FROM OPERACION O
        JOIN INVENTARIO I ON O.Cod_inv = I.Cod_inv
        JOIN INSUMOS P ON I.Cod_ins = P.Cod_ins
        ORDER BY O.Fecha DESC, O.Hora DESC
    """)
    
    movimientos = cursor.fetchall()
    
    if movimientos:
        df = pd.DataFrame([{
            "Código Operación": row.cod_ope,
            "Producto": row.Producto,
            "Lote": row.Lote,
            "Tipo de Operación": row.Tipo_Operacion,
            "Cantidad": row.Cantidad,
            "Fecha": str(row.Fecha),
            "Hora": str(row.Hora),
            "Motivo": row.Motivo
        } for row in movimientos])
        
        st.dataframe(df, use_container_width=True, height=600)
    else:
        st.info("No hay movimientos registrados.")
        filtro = st.selectbox("Filtrar por tipo:", ["Todos", "Ingreso", "Salida"])