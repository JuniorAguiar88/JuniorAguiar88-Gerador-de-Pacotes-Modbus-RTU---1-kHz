/**
 * MÓDULO: GERADOR DE PACOTES DE CONFIGURAÇÃO
 * 
 * O QUE ESTE MÓDULO FAZ:
 * Cria mensagens de CONFIGURAÇÃO do sistema. São como "listas de endereços" 
 * que dizem para o sistema quais sensores existem e seus números de identificação.
 * 
 * ESTRUTURA DA MENSAGEM (24 bytes no total):
 * 
 * POSIÇÃO | CONTEÚDO          | TAMANHO | EXEMPLO
 * --------|-------------------|---------|---------
 * 0       | Cabeçalho         | 1 byte  | 0xAA
 * 1       | Quantidade        | 1 byte  | 0x0A
 * 2-3     | Sensor 1 ID       | 2 bytes | 0x10 0x00
 * 4-5     | Sensor 2 ID       | 2 bytes | 0x10 0x0A
 * ...     | ...               | ...     | ...
 * 20-21   | Sensor 10 ID      | 2 bytes | 0x10 0x5A
 * 22-23   | Verificador CRC   | 2 bytes | 0x2F 0x8A (ex: little-endian de 0x8A2F)
 * 
 * PORQUE 24 BYTES?
 * 1 (cabeçalho) + 1 (quantidade) + 10×2 (IDs) + 2 (CRC) = 24 bytes
 */

#ifndef PACOTE_CONFIGURACAO_H
#define PACOTE_CONFIGURACAO_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "pico/stdlib.h"
#include "display.h"

#define NUM_CANAIS 10
#define MODBUS_HEADER_CONFIG 0xAA
#define MODBUS_CHANNEL_COUNT 0x0A


#define TAMANHO_PACOTE_CONFIG 24

uint16_t calcular_crc16_modbus(uint8_t *data, size_t length);
bool verificar_integridade_crc(uint8_t *data, size_t length);
void gerar_ids_canais(uint16_t ids_canais[]);
size_t criar_pacote_configuracao_modbus(uint8_t pacote[], uint16_t ids_canais[]);
void exibir_pacote_configuracao(uint8_t pacote[], size_t tamanho_pacote, 
                               uint16_t ids_canais[], uint32_t contador_pacotes);
void exibir_configuracao_no_display(uint16_t crc, uint16_t ids_canais[], 
                                   uint32_t contador_pacotes);
void gerar_pacote_configuracao(uint16_t ids_canais[], uint32_t *contador_pacotes);

/**
 * @brief Gera apenas os IDs dos canais sem criar pacote
 * 
 * @param ids_canais Array para armazenar os IDs gerados
 * @param sequencial true para IDs sequenciais, false para fixos
 */
void gerar_apenas_ids_canais(uint16_t ids_canais[], bool sequencial);



#endif // PACOTE_CONFIGURACAO_H