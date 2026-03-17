/**
 * MÓDULO: GERADOR DE PACOTES DE DADOS MODBUS RTU (22 bytes)
 * 
 * DESCRIÇÃO:
 * Gera mensagens de DADOS do sistema (enviadas 990 vezes por segundo)
 * Contém leituras simuladas de tensão dos 10 canais.
 * 
 * ESTRUTURA DO PACOTE DE DADOS (22 bytes):
 * - Header: 1 byte (0x55)
 * - Empty: 1 byte (0x00)
 * - Channel Data[0] to [9]: 20 bytes (10 × 2 bytes uint16_t big-endian)
 */

#ifndef PACOTE_DADOS_H
#define PACOTE_DADOS_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
// REMOVIDO: #include "hardware/uart.h"  // Não é mais necessário

// ============================================================================
// CONSTANTES DE CONFIGURAÇÃO
// ============================================================================

/** Número de canais/sensores no sistema */
#define NUM_CANAIS 10

/** Tensão máxima que pode ser medida (0.0V a 3.3V) */
#define MAX_TENSAO 3.3f

/** Cabeçalho identificador do pacote de dados */
#define MODBUS_HEADER_DADOS 0x55

/** Cabeçalho identificador do pacote de configuração */
#define MODBUS_HEADER_CONFIG 0xAA

/** Byte vazio (sincronismo) */
#define MODBUS_EMPTY_BYTE 0x00

/** Tamanho total do pacote de dados em bytes */
#define TAMANHO_PACOTE_DADOS 22  // 1(header) + 1(empty) + 20(data)

// ============================================================================
// PROTÓTIPOS DAS FUNÇÕES PÚBLICAS
// ============================================================================

/**
 * @brief Gera valores aleatórios de tensão para simular leituras de sensores
 * 
 * @param tensoes_canais Array para armazenar as tensões geradas (0.0V a 3.3V)
 */
void gerar_tensoes_canais(float tensoes_canais[]);

/**
 * @brief Cria um pacote de dados com tensões incluídas (22 bytes)
 * 
 * @param pacote Buffer para armazenar o pacote gerado
 * @param tensoes_canais Array com as tensões dos canais
 * @return size_t Tamanho do pacote gerado (deve ser TAMANHO_PACOTE_DADOS)
 */
size_t criar_pacote_dados_modbus(uint8_t pacote[], float tensoes_canais[]);

/**
 * @brief Exibe informações do pacote de dados no terminal serial
 * 
 * @param pacote Pacote de dados
 * @param tamanho_pacote Tamanho do pacote
 * @param tensoes_canais Valores de tensão medidos
 * @param contador_pacotes Contador global de pacotes
 */
void exibir_pacote_dados(uint8_t pacote[], size_t tamanho_pacote, 
                        float tensoes_canais[], uint32_t contador_pacotes);

/**
 * @brief Exibe informações resumidas no display OLED
 * 
 * @param tensoes_canais Valores de tensão medidos
 * @param contador_pacotes Contador global de pacotes
 */
void exibir_dados_no_display(float tensoes_canais[], uint32_t contador_pacotes);

/**
 * @brief Função principal do módulo - gera e processa um pacote de dados
 * 
 * @param tensoes_canais Array para armazenar as tensões geradas
 * @param contador_pacotes Ponteiro para o contador global de pacotes
 */
void gerar_pacote_dados(float tensoes_canais[], uint32_t *contador_pacotes);

#endif // PACOTE_DADOS_H