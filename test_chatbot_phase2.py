import asyncio
import json
from datetime import datetime
from typing import Dict, Any

# Test completo de la Fase 2: Chatbot e IA Assistant

class Phase2Tester:
    def __init__(self):
        self.test_results = []
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Ejecuta todos los tests de la Fase 2"""
        
        print("🚀 Iniciando tests de Fase 2: Chatbot e IA Assistant")
        print("=" * 60)
        
        # Tests individuales
        await self.test_ai_assistant()
        await self.test_conversation_manager()
        await self.test_webhooks()
        await self.test_whatsapp_service()
        await self.test_interaction_model()
        await self.test_integration_flow()
        
        # Generar reporte
        return self.generate_report()
    
    async def test_ai_assistant(self):
        """Test del AI Assistant"""
        
        print("\n🤖 Testing AI Assistant...")
        
        try:
            from app.services.ai_assistant import AIAssistant
            
            ai = AIAssistant()
            
            # Test 1: Inicialización
            assert ai.knowledge_base is not None, "Knowledge base no cargada"
            self.log_success("AI Assistant", "Inicialización correcta")
            
            # Test 2: Clasificación de intenciones
            intent, confidence = ai._classify_intent("Quiero ver precios")
            assert intent == "pricing", f"Intención incorrecta: {intent}"
            assert confidence > 0, f"Confianza muy baja: {confidence}"
            self.log_success("AI Assistant", "Clasificación de intenciones")
            
            # Test 3: Detección de señales de compra
            buying_signals = ai._detect_buying_signals("Quiero comprar el producto")
            assert buying_signals == True, "No detectó señales de compra"
            self.log_success("AI Assistant", "Detección de señales de compra")
            
            # Test 4: Análisis de sentiment
            sentiment = await ai._analyze_sentiment("Excelente producto, me gusta mucho")
            assert sentiment > 0, f"Sentiment debería ser positivo: {sentiment}"
            self.log_success("AI Assistant", "Análisis de sentiment")
            
            print("✅ AI Assistant: Todos los tests pasaron")
            
        except Exception as e:
            self.log_error("AI Assistant", str(e))
            print(f"❌ AI Assistant: Error - {e}")
    
    async def test_conversation_manager(self):
        """Test del Conversation Manager"""
        
        print("\n💬 Testing Conversation Manager...")
        
        try:
            from app.services.conversation_manager import ConversationManager
            
            cm = ConversationManager()
            
            # Test 1: Inicialización
            assert cm.context_window > 0, "Context window no configurado"
            self.log_success("Conversation Manager", "Inicialización")
            
            # Test 2: Cálculo de engagement score
            test_context = {
                "total_messages": 10,
                "duration_minutes": 15,
                "primary_intent": "pricing",
                "sentiment_trend": "positive"
            }
            
            engagement = cm._calculate_engagement_score(test_context)
            assert 0 <= engagement <= 1, f"Engagement score fuera de rango: {engagement}"
            assert engagement > 0.5, f"Engagement score muy bajo para conversación activa: {engagement}"
            self.log_success("Conversation Manager", "Cálculo de engagement score")
            
            # Test 3: Cálculo de satisfaction score
            satisfaction = cm._calculate_satisfaction_score(test_context)
            assert 0 <= satisfaction <= 1, f"Satisfaction score fuera de rango: {satisfaction}"
            self.log_success("Conversation Manager", "Cálculo de satisfaction score")
            
            print("✅ Conversation Manager: Todos los tests pasaron")
            
        except Exception as e:
            self.log_error("Conversation Manager", str(e))
            print(f"❌ Conversation Manager: Error - {e}")
    
    async def test_webhooks(self):
        """Test de Webhooks"""
        
        print("\n🔗 Testing Webhooks...")
        
        try:
            # Test 1: Importación de módulos
            from app.api.webhooks import router
            assert router is not None, "Router de webhooks no disponible"
            self.log_success("Webhooks", "Importación de módulos")
            
            # Test 2: Verificar rutas definidas
            routes = [route.path for route in router.routes]
            expected_routes = ["/webhooks/whatsapp", "/webhooks/telegram", "/webhooks/hubspot", "/webhooks/test"]
            
            for expected_route in expected_routes:
                if any(expected_route in route for route in routes):
                    self.log_success("Webhooks", f"Ruta {expected_route} configurada")
                else:
                    self.log_warning("Webhooks", f"Ruta {expected_route} no encontrada")
            
            print("✅ Webhooks: Tests básicos pasaron")
            
        except Exception as e:
            self.log_error("Webhooks", str(e))
            print(f"❌ Webhooks: Error - {e}")
    
    async def test_whatsapp_service(self):
        """Test del WhatsApp Service"""
        
        print("\n📱 Testing WhatsApp Service...")
        
        try:
            from app.services.integrations.whatsapp_service import WhatsAppService
            
            wa = WhatsAppService()
            
            # Test 1: Inicialización
            assert hasattr(wa, 'access_token'), "Access token no configurado"
            assert hasattr(wa, 'phone_number_id'), "Phone number ID no configurado"
            self.log_success("WhatsApp Service", "Inicialización")
            
            # Test 2: Creación de botones de servicio
            buttons = wa.create_service_buttons()
            assert len(buttons) == 3, f"Número incorrecto de botones: {len(buttons)}"
            assert all('id' in btn and 'title' in btn for btn in buttons), "Formato de botones incorrecto"
            self.log_success("WhatsApp Service", "Creación de botones")
            
            # Test 3: Creación de secciones de productos
            products = [
                {"name": "Producto Test", "price": "100", "description": "Test"}
            ]
            sections = wa.create_product_list_sections(products)
            assert len(sections) > 0, "No se crearon secciones"
            assert 'rows' in sections[0], "Formato de secciones incorrecto"
            self.log_success("WhatsApp Service", "Creación de listas de productos")
            
            print("✅ WhatsApp Service: Todos los tests pasaron")
            
        except Exception as e:
            self.log_error("WhatsApp Service", str(e))
            print(f"❌ WhatsApp Service: Error - {e}")
    
    async def test_interaction_model(self):
        """Test del Modelo de Interacciones"""
        
        print("\n💾 Testing Interaction Model...")
        
        try:
            from app.models.interaction import Interaction, ConversationSummary, generate_conversation_id
            from app.models.interaction import ConversationStatus, MessageType, Platform
            
            # Test 1: Enums definidos correctamente
            assert ConversationStatus.ACTIVE == "active", "ConversationStatus.ACTIVE incorrecto"
            assert MessageType.TEXT == "text", "MessageType.TEXT incorrecto"
            assert Platform.WHATSAPP == "whatsapp", "Platform.WHATSAPP incorrecto"
            self.log_success("Interaction Model", "Enums definidos")
            
            # Test 2: Generación de conversation_id
            conv_id = generate_conversation_id()
            assert len(conv_id) > 10, "Conversation ID muy corto"
            assert conv_id != generate_conversation_id(), "Conversation IDs no son únicos"
            self.log_success("Interaction Model", "Generación de conversation_id")
            
            # Test 3: Estructura de modelos
            assert hasattr(Interaction, 'conversation_id'), "Interaction.conversation_id no existe"
            assert hasattr(Interaction, 'intent_detected'), "Interaction.intent_detected no existe"
            assert hasattr(ConversationSummary, 'engagement_score'), "ConversationSummary.engagement_score no existe"
            self.log_success("Interaction Model", "Estructura de modelos")
            
            print("✅ Interaction Model: Todos los tests pasaron")
            
        except Exception as e:
            self.log_error("Interaction Model", str(e))
            print(f"❌ Interaction Model: Error - {e}")
    
    async def test_integration_flow(self):
        """Test del flujo completo de integración"""
        
        print("\n🔄 Testing Integration Flow...")
        
        try:
            # Simular flujo completo: Mensaje → AI → Respuesta
            
            # Test 1: Flujo básico sin base de datos
            test_message = "Hola, quiero información sobre precios"
            test_phone = "+1234567890"
            
            # Simular proceso del AI Assistant
            from app.services.ai_assistant import AIAssistant
            ai = AIAssistant()
            
            intent, confidence = ai._classify_intent(test_message)
            buying_signals = ai._detect_buying_signals(test_message)
            
            assert intent is not None, "No se clasificó intención"
            assert confidence > 0, "Confianza en clasificación es 0"
            
            self.log_success("Integration Flow", "Flujo básico de procesamiento")
            
            # Test 2: Respuesta de fallback
            fallback_response = ai._get_fallback_response("pricing")
            assert len(fallback_response) > 10, "Respuesta de fallback muy corta"
            assert "precio" in fallback_response.lower() or "plan" in fallback_response.lower(), "Respuesta no relacionada con pricing"
            
            self.log_success("Integration Flow", "Respuestas de fallback")
            
            print("✅ Integration Flow: Tests básicos pasaron")
            
        except Exception as e:
            self.log_error("Integration Flow", str(e))
            print(f"❌ Integration Flow: Error - {e}")
    
    def log_success(self, component: str, test: str):
        """Registra un test exitoso"""
        self.test_results.append({
            "component": component,
            "test": test,
            "status": "SUCCESS",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_error(self, component: str, error: str):
        """Registra un error en test"""
        self.test_results.append({
            "component": component,
            "test": "Error",
            "status": "ERROR",
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_warning(self, component: str, warning: str):
        """Registra una advertencia"""
        self.test_results.append({
            "component": component,
            "test": "Warning",
            "status": "WARNING",
            "warning": warning,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def generate_report(self) -> Dict[str, Any]:
        """Genera reporte final de tests"""
        
        total_tests = len(self.test_results)
        successful_tests = len([r for r in self.test_results if r["status"] == "SUCCESS"])
        error_tests = len([r for r in self.test_results if r["status"] == "ERROR"])
        warning_tests = len([r for r in self.test_results if r["status"] == "WARNING"])
        
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "successful": successful_tests,
                "errors": error_tests,
                "warnings": warning_tests,
                "success_rate": f"{success_rate:.1f}%"
            },
            "phase_2_status": "COMPLETED" if success_rate >= 80 else "NEEDS_WORK",
            "detailed_results": self.test_results,
            "next_steps": self.get_next_steps(success_rate),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Mostrar reporte en consola
        print("\n" + "="*60)
        print("📊 REPORTE DE TESTS - FASE 2")
        print("="*60)
        print(f"Total de tests: {total_tests}")
        print(f"✅ Exitosos: {successful_tests}")
        print(f"❌ Errores: {error_tests}")
        print(f"⚠️  Advertencias: {warning_tests}")
        print(f"📈 Tasa de éxito: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("\n🎉 FASE 2 COMPLETADA - Chatbot e IA Assistant listos!")
        else:
            print("\n🔧 FASE 2 NECESITA TRABAJO - Revisar errores antes de continuar")
        
        print("\n📋 Próximos pasos:")
        for step in report["next_steps"]:
            print(f"  • {step}")
        
        return report
    
    def get_next_steps(self, success_rate: float) -> list:
        """Determina próximos pasos basado en resultados"""
        
        if success_rate >= 80:
            return [
                "✅ Proceder con testing en entorno de desarrollo",
                "🔗 Configurar webhooks reales de WhatsApp/Telegram",
                "📊 Implementar monitoring y logging",
                "🚀 Comenzar Fase 3: Nurturing Automation"
            ]
        else:
            return [
                "🔧 Corregir errores identificados en los tests",
                "⚙️ Completar configuración de servicios faltantes",
                "🧪 Ejecutar tests nuevamente hasta lograr >80% éxito",
                "📚 Revisar documentación de integración"
            ]

# Función principal para ejecutar tests
async def main():
    """Ejecuta todos los tests de Fase 2"""
    
    tester = Phase2Tester()
    report = await tester.run_all_tests()
    
    # Guardar reporte en archivo
    with open("phase2_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Reporte guardado en: phase2_test_report.json")
    
    return report

if __name__ == "__main__":
    # Ejecutar tests
    asyncio.run(main())