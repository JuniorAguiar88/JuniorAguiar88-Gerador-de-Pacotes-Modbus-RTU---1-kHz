# test_class.py
import modbus_reader

print("Conteúdo de modbus_reader:")
print(dir(modbus_reader))

if hasattr(modbus_reader, 'ModbusReader'):
    print("✅ ModbusReader existe!")
else:
    print("❌ ModbusReader NÃO existe")

# Tente instanciar
try:
    r = modbus_reader.ModbusReader()
    print("✅ Instância criada com sucesso!")
except Exception as e:
    print(f"❌ Erro ao instanciar: {e}")