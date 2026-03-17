/**
 * MÓDULO: IMPLEMENTAÇÃO DO GERADOR DE PACOTES DE DADOS (22 bytes)
 * 
 * O QUE ESTE ARQUIVO FAZ:
 * Contém todas as funções que executam o trabalho pesado de criar mensagens 
 * de dados com valores de tensão incluídos, no formato de 22 bytes.
 */

#include "pacote_dados.h"
#include "display.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
// REMOVIDO: #include "hardware/uart.h"  // Não é mais necessário

// =============================================================================

/**
 * @brief Converte tensão (0.0–3.3V) para uint16_t (0–65535)
 */
uint16_t tensao_to_uint16(float tensao) {
    if (tensao < 0.0f) tensao = 0.0f;
    if (tensao > 3.3f) tensao = 3.3f;
    return (uint16_t)(tensao * 65535.0f / 3.3f);
}

// =============================================================================

/**
 * @brief Gera valores aleatórios de tensão para simular leituras de sensores
 */
void gerar_tensoes_canais(float tensoes_canais[]) {
    for(int i = 0; i < NUM_CANAIS; i++) {
        int numero_aleatorio = rand();
        float normalizado = (float)numero_aleatorio / (float)RAND_MAX;
        tensoes_canais[i] = normalizado * MAX_TENSAO;
    }
}

// =============================================================================

/**
 * @brief Cria um pacote de dados Modbus com tensões incluídas (22 bytes)
 */
size_t criar_pacote_dados_modbus(uint8_t pacote[], float tensoes_canais[]) {
    if (pacote == NULL || tensoes_canais == NULL) {
        return 0;
    }
    
    int index = 0;
    
    // === BYTE 0: CABEÇALHO ===
    pacote[index++] = MODBUS_HEADER_DADOS; // 0x55
    
    // === BYTE 1: EMPTY BYTE ===
    pacote[index++] = MODBUS_EMPTY_BYTE;   // 0x00
    
    // === BYTES 2-21: ARRAY DE TENSÕES (20 bytes) ===
    for(int i = 0; i < NUM_CANAIS; i++) {
        uint16_t valor = tensao_to_uint16(tensoes_canais[i]);
        
        // Armazena em big-endian (high byte first)
        pacote[index++] = (valor >> 8) & 0xFF;  // HIGH BYTE
        pacote[index++] = valor & 0xFF;         // LOW BYTE
    }
    
    if (index != TAMANHO_PACOTE_DADOS) {
        printf("AVISO: Tamanho do pacote de dados inconsistente: %d vs %d\n", 
               index, TAMANHO_PACOTE_DADOS);
    }
    
    return index;
}

// =============================================================================

/**
 * @brief Exibe informações do pacote de dados no terminal serial
 */
void exibir_pacote_dados(uint8_t pacote[], size_t tamanho_pacote, 
                        float tensoes_canais[], uint32_t contador_pacotes) {
    if (pacote == NULL || tamanho_pacote < TAMANHO_PACOTE_DADOS || 
        tensoes_canais == NULL) {
        printf("ERRO: Parâmetros inválidos para exibir pacote\n");
        return;
    }
    
    printf("DADOS  [%lu] - %dB | Tensoes: ",
           contador_pacotes, TAMANHO_PACOTE_DADOS);
    
    for(int i = 0; i < 3; i++) {
        printf("%.2fV ", tensoes_canais[i]);
    }
    printf("...\n");
    
    if (contador_pacotes % 1000 == 0) {
        printf("  [HEX] ");
        for(int i = 0; i < 16 && i < TAMANHO_PACOTE_DADOS; i++) {
            printf("%02X ", pacote[i]);
        }
        if (TAMANHO_PACOTE_DADOS > 16) printf("...");
        printf("\n");
        
        printf("  [VALORES] ");
        for(int i = 0; i < 3; i++) {
            printf("Ch%d:%.3fV ", i, tensoes_canais[i]);
        }
        printf("\n");
    }
}

// =============================================================================

/**
 * @brief Exibe informações resumidas no display OLED
 */
void exibir_dados_no_display(float tensoes_canais[], uint32_t contador_pacotes) {
    char buffer[24];
    clear_display();
    
    snprintf(buffer, sizeof(buffer), "DADOS #%lu", contador_pacotes);
    display_text_no_clear(buffer, 0, 0, 1);
    
    snprintf(buffer, sizeof(buffer), "%dB", TAMANHO_PACOTE_DADOS);
    display_text_no_clear(buffer, 64, 0, 1);
    
    snprintf(buffer, sizeof(buffer), "T0:%.2fV", tensoes_canais[0]);
    display_text_no_clear(buffer, 0, 16, 1);
    
    snprintf(buffer, sizeof(buffer), "T1:%.2fV", tensoes_canais[1]);
    display_text_no_clear(buffer, 0, 32, 1);
    
    snprintf(buffer, sizeof(buffer), "T2:%.2fV", tensoes_canais[2]);
    display_text_no_clear(buffer, 64, 32, 1);
    
    show_display();
}

// =============================================================================

/**
 * @brief Função principal do módulo - gera e processa um pacote de dados
 */
void gerar_pacote_dados(float tensoes_canais[], uint32_t *contador_pacotes) {
    if (tensoes_canais == NULL || contador_pacotes == NULL) {
        return;
    }
    
    gerar_tensoes_canais(tensoes_canais);
    
    uint8_t pacote_dados[TAMANHO_PACOTE_DADOS];
    size_t tamanho_dados = criar_pacote_dados_modbus(pacote_dados, tensoes_canais);
    
    if (tamanho_dados != TAMANHO_PACOTE_DADOS) {
        return;
    }
    
    // ✅ ENVIAR VIA USB CDC (não UART) - 22 bytes binários puros
    fwrite(pacote_dados, 1, TAMANHO_PACOTE_DADOS, stdout);
    fflush(stdout);  // força envio imediato

    // Opcional: log no display (não no USB)
    exibir_dados_no_display(tensoes_canais, *contador_pacotes);
}