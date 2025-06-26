#!/usr/bin/env python3
"""
Script de migração para atualizar a estrutura das instruções dos modelos
"""

import os
import sys
from datetime import datetime, timezone

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, ModelInstructions, GeneralInstructions

def migrate_instructions():
    """Migra a estrutura antiga das instruções para a nova"""
    
    with app.app_context():
        print("🔄 Iniciando migração das instruções dos modelos...")
        
        # Verificar se a tabela antiga ainda existe (com campos persona, restrictions, etc.)
        try:
            # Tentar acessar um registro antigo
            old_instructions = db.session.execute(
                "SELECT model_id, persona, restrictions, introduction, conclusion, is_active FROM model_instructions LIMIT 1"
            ).fetchone()
            
            if old_instructions:
                print("📋 Encontrada estrutura antiga. Migrando dados...")
                
                # Buscar todas as instruções antigas
                old_records = db.session.execute(
                    "SELECT model_id, persona, restrictions, introduction, conclusion, is_active FROM model_instructions"
                ).fetchall()
                
                # Migrar cada registro
                for record in old_records:
                    model_id, persona, restrictions, introduction, conclusion = record[0], record[1], record[2], record[3], record[4]
                    is_active = record[5]
                    
                    # Combinar todos os campos em uma única instrução
                    new_instructions = ""
                    
                    if persona:
                        new_instructions += f"Você é: {persona}\n\n"
                    
                    if restrictions:
                        new_instructions += f"Restrições: {restrictions}\n\n"
                    
                    if introduction:
                        new_instructions += f"Introdução: {introduction}\n\n"
                    
                    if conclusion:
                        new_instructions += f"Conclusão: {conclusion}\n\n"
                    
                    # Remover espaços extras no final
                    new_instructions = new_instructions.strip()
                    
                    # Verificar se já existe uma instrução nova para este modelo
                    existing = ModelInstructions.query.filter_by(model_id=model_id).first()
                    if existing:
                        # Atualizar a existente
                        existing.instructions = new_instructions
                        existing.is_active = is_active
                        existing.updated_at = datetime.now(timezone.utc)
                        print(f"  ✅ Atualizado modelo: {model_id}")
                    else:
                        # Criar nova
                        new_instruction = ModelInstructions(
                            model_id=model_id,
                            instructions=new_instructions,
                            is_active=is_active
                        )
                        db.session.add(new_instruction)
                        print(f"  ✅ Migrado modelo: {model_id}")
                
                # Remover a tabela antiga
                print("🗑️ Removendo estrutura antiga...")
                db.session.execute("DROP TABLE model_instructions")
                
                # Recriar a tabela com a nova estrutura
                print("🏗️ Recriando tabela com nova estrutura...")
                db.create_all()
                
                print("✅ Migração concluída com sucesso!")
                
            else:
                print("✅ Estrutura já está atualizada.")
                
        except Exception as e:
            print(f"ℹ️ Estrutura antiga não encontrada ou já migrada: {e}")
            print("✅ Continuando com a estrutura atual...")
        
        # Verificar se existem instruções gerais
        if not GeneralInstructions.query.first():
            print("📝 Criando instruções gerais padrão...")
            default_instructions = """Você é um juiz experiente especializado em direito civil, com mais de 20 anos de experiência no Poder Judiciário. 

Suas decisões devem ser baseadas apenas nos fatos apresentados e na legislação aplicável. Use linguagem formal e técnica apropriada para documentos judiciais.

Não mencione nomes de pessoas físicas ou jurídicas específicas. Não faça suposições sobre fatos não apresentados. Base suas decisões apenas nos dados fornecidos e na legislação aplicável."""
            
            general_instructions = GeneralInstructions(instructions=default_instructions)
            db.session.add(general_instructions)
            db.session.commit()
            print("✅ Instruções gerais criadas!")
        
        print("🎉 Migração finalizada!")

if __name__ == '__main__':
    migrate_instructions() 