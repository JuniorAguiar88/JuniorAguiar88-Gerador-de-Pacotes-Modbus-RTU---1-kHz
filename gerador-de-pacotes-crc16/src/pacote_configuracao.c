/**
 * MÓDULO: IMPLEMENTAÇÃO DO GERADOR DE PACOTES DE CONFIGURAÇÃO
 * Contém todas as funções que executam o trabalho de criar mensagens 
 * de configuração.
 */

#include "pacote_configuracao.h"


// FUNÇÃO: calcular_crc16_modbus - O DETECTOR DE ERROS

uint16_t calcular_crc16_modbus(uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF; // Valor inicial Modbus
    
    for (size_t i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i]; // XOR com byte atual
        
        // Processa cada bit (8 bits por byte)
        for (int j = 0; j < 8; j++) {
            // Verifica se o bit menos significativo é 1
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001; // Polinômio reverso
            } else {
                crc >>= 1; // Apenas shift right
            }
        }
    }
    
    return crc; // CRC final
}


// FUNÇÃO: verificar_integridade_crc - O FISCAL DE QUALIDADE


bool verificar_integridade_crc(uint8_t *data, size_t length) {
    if (length < 2) { // tamanho mínimo para ter CRC
        return false;
    }
    
    // Extrai CRC recebido (little-endian)
    uint16_t crc_recebido = (data[length - 1] << 8) | data[length - 2];
    // Calcula CRC sobre dados (excluindo os 2 bytes do CRC)
    uint16_t crc_calculado = calcular_crc16_modbus(data, length - 2);
    
    return (crc_calculado == crc_recebido);
}


void gerar_apenas_ids_canais(uint16_t ids_canais[], bool sequencial) {
    // Mesma lógica de gerar_ids_canais mas sem print
    static uint16_t sequencia_global = 0;
    
    if (sequencial) {
        uint16_t base_id = 0x1000 + (sequencia_global % 0x100);
        
        for (int i = 0; i < NUM_CANAIS; i++) {
            ids_canais[i] = base_id + (i * 10);
            
            if (ids_canais[i] < 0x1000 || ids_canais[i] > 0xFFFF) {
                ids_canais[i] = 0x1000 + ((base_id + i) % 0xF000);
            }
        }
        
        sequencia_global++;
        if (sequencia_global > 0xFF) sequencia_global = 0;
    } else {
        uint16_t base_id = 0x1000;
        
        for (int i = 0; i < NUM_CANAIS; i++) {
            ids_canais[i] = base_id + (i * 10);
            
            if (ids_canais[i] == 0) {
                ids_canais[i] = 0x1000 + i;
            }
        }
    }
}

void gerar_ids_canais(uint16_t ids_canais[]) {
    // Usar a função existente com valor padrão (sequencial = true)
    gerar_apenas_ids_canais(ids_canais, true);
}


// FUNÇÃO: criar_pacote_configuracao_modbus - O MONTADOR DE MENSAGENS


size_t criar_pacote_configuracao_modbus(uint8_t pacote[], uint16_t ids_canais[]) {
    int index = 0; // Controle absoluto de posição
    
    // === BYTE 0: CABEÇALHO ===
    pacote[index++] = MODBUS_HEADER_CONFIG; // 0xAA
    
    // === BYTE 1: CONTAGEM ===  
    pacote[index++] = MODBUS_CHANNEL_COUNT; // 0x0A
    
    // === BYTES 2-21: ARRAY DE IDs ===
    for (int i = 0; i < NUM_CANAIS; i++) {
        pacote[index++] = (ids_canais[i] >> 8) & 0xFF; // HIGH BYTE
        pacote[index++] = ids_canais[i] & 0xFF; // LOW BYTE 
    }
    
    // Calcular CRC sobre os primeiros 22 bytes -> 0-21 (header + count + 10×IDs)
    uint16_t crc = calcular_crc16_modbus(pacote, index); // index == 22 aqui
    
    // Anexar CRC em little-endian (byte baixo primeiro)
    pacote[index++] = crc & 0xFF; // LOW BYTE do CRC
    pacote[index++] = (crc >> 8) & 0xFF; // HIGH BYTE do CRC
    
    // Total: 24 bytes
    return TAMANHO_PACOTE_CONFIG; // HIGH BYTE do CRC
}


// FUNÇÃO: exibir_pacote_configuracao


void exibir_pacote_configuracao(uint8_t pacote[], size_t tamanho_pacote, 
                               uint16_t ids_canais[], uint32_t contador_pacotes) {
    // Extrair CRC dos últimos 2 bytes (little-endian)
    uint16_t crc = (pacote[tamanho_pacote - 1] << 8) | 
                   pacote[tamanho_pacote - 2];
    
    printf("CONFIG [%lu] - %dB - CRC:0x%04X | IDs: ",
           contador_pacotes, TAMANHO_PACOTE_CONFIG, crc);
    
    for (int i = 0; i < 3; i++) {
        printf("%04X ", ids_canais[i]);
    }
    printf("...\n");
}


// FUNÇÃO: exibir_configuracao_no_display - O PAINEL DE CONTROLE


void exibir_configuracao_no_display(uint16_t crc, uint16_t ids_canais[], 
                                   uint32_t contador_pacotes) {
    char buffer[24];
    clear_display();
    
    snprintf(buffer, sizeof(buffer), "CONFIG #%lu", contador_pacotes);
    display_text_no_clear(buffer, 0, 0, 1);
    
    snprintf(buffer, sizeof(buffer), "Tam: %d bytes", TAMANHO_PACOTE_CONFIG);
    display_text_no_clear(buffer, 0, 12, 1);
    
    snprintf(buffer, sizeof(buffer), "CRC: %04X", crc);
    display_text_no_clear(buffer, 0, 24, 1);
    
    snprintf(buffer, sizeof(buffer), "ID0: %04X", ids_canais[0]);
    display_text_no_clear(buffer, 0, 36, 1);
    
    snprintf(buffer, sizeof(buffer), "ID1: %04X", ids_canais[1]);
    display_text_no_clear(buffer, 64, 36, 1);
    
    show_display();
}


// FUNÇÃO: gerar_pacote_configuracao - Função principal do módulo
void gerar_pacote_configuracao(uint16_t ids_canais[], uint32_t *contador_pacotes) {
    if (ids_canais == NULL || contador_pacotes == NULL) {
        printf("ERRO: Parâmetros inválidos para gerar pacote\n");
        return;
    }
    
    // NÃO gerar novos IDs automaticamente
    // A função chamadora decide se gera novos IDs ou usa os existentes
    // Se ids_canais já estiver preenchido, mantém os valores
    
    // Criar pacote
    uint8_t pacote_config[TAMANHO_PACOTE_CONFIG];
    size_t tamanho_config = criar_pacote_configuracao_modbus(pacote_config, ids_canais);
    
    if (tamanho_config != TAMANHO_PACOTE_CONFIG) {
        printf("ERRO: Tamanho do pacote incorreto: %zu vs %d\n", 
               tamanho_config, TAMANHO_PACOTE_CONFIG);
        return;
    }
    
    // Extrair CRC para exibição
    uint16_t crc_config = (pacote_config[tamanho_config - 1] << 8) |
                          pacote_config[tamanho_config - 2];
    
    // Exibir no terminal
    exibir_pacote_configuracao(pacote_config, tamanho_config, ids_canais, *contador_pacotes);
    
    // Exibir no display
    exibir_configuracao_no_display(crc_config, ids_canais, *contador_pacotes);
    
    // Auto-verificação de integridade
    bool config_valido = verificar_integridade_crc(pacote_config, tamanho_config);
    if (!config_valido) {
        printf("ERRO CRÍTICO: Pacote de configuração corrompido!\n");
        
        // Feedback visual de erro
        clear_display();
        display_text_no_clear("ERRO CRC", 0, 0, 2);
        display_text_no_clear("CONFIG", 0, 24, 1);
        show_display();
        sleep_ms(1000);
    }
    
    printf("  [CONFIG] Pacote de configuração válido: %s\n", 
           config_valido ? "SIM" : "NÃO");
}