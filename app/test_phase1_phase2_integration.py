"""
PowerTrader AI+ Phase 1 & 2 Integration Test
Comprehensive test suite for all modular components
"""

import os
import sys
import time
import tempfile
import json
from datetime import datetime

def test_imports():
    """Test that all new modular components can be imported."""
    print("=" * 60)
    print("TESTING IMPORTS")
    print("=" * 60)
    
    try:
        # Test logging system
        from pt_logging_system import setup_logging, log_info, log_warning, log_error
        print("✓ Logging system imported successfully")
        
        # Test caching system
        from pt_caching_system import MemoryCache, PersistentCache, CacheManager
        print("✓ Caching system imported successfully")
        
        # Test theme manager
        from pt_theme_manager import setup_dark_theme, ThemeManager, get_default_colors
        print("✓ Theme manager imported successfully")
        
        # Test async patterns
        from pt_async_patterns import AsyncHTTPClient, AsyncFileManager, AsyncTaskQueue
        print("✓ Async patterns imported successfully")
        
        # Test process manager
        from pt_process_manager import ProcessManager, LogProc, ProcInfo
        print("✓ Process manager imported successfully")
        
        # Test settings manager
        from pt_settings_manager import SettingsManager, get_settings_manager
        print("✓ Settings manager imported successfully")
        
        # Test neural network implementation
        from pt_neural_network import TradingLSTM, TradingTransformer, FeatureEngineering, ModelTrainer
        print("✓ Neural network system imported successfully")
        
        # Test model evaluation
        from pt_model_evaluation import ModelEvaluator, TradingBacktest
        print("✓ Model evaluation system imported successfully")
        
        print("\n✓ ALL IMPORTS SUCCESSFUL!")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_logging_system():
    """Test the logging system functionality."""
    print("\n" + "=" * 60)
    print("TESTING LOGGING SYSTEM")
    print("=" * 60)
    
    try:
        from pt_logging_system import setup_logging, log_info, log_warning, log_error, log_trade
        
        # Setup logging in a temp directory
        temp_dir = tempfile.mkdtemp()
        log_dir = os.path.join(temp_dir, "logs")
        
        setup_logging(log_dir=log_dir, app_name="test_app", log_level="DEBUG")
        print("✓ Logging system setup completed")
        
        # Test different log levels
        log_info("Test info message")
        log_warning("Test warning message") 
        log_error("Test error message")
        log_trade("Test trade message")
        print("✓ All log levels working")
        
        # Check if log files were created
        if os.path.exists(log_dir):
            log_files = os.listdir(log_dir)
            if log_files:
                print(f"✓ Log files created: {log_files}")
            else:
                print("⚠ No log files created")
        
        return True
        
    except Exception as e:
        print(f"✗ Logging system test failed: {e}")
        return False


def test_caching_system():
    """Test the caching system functionality."""
    print("\n" + "=" * 60)
    print("TESTING CACHING SYSTEM")
    print("=" * 60)
    
    try:
        from pt_caching_system import MemoryCache, CacheManager
        
        # Test memory cache
        cache = MemoryCache(max_size=10, max_memory_mb=1)
        
        # Test basic operations
        cache.put("test_key", {"data": "test_value"}, ttl_seconds=60)
        cached_value = cache.get("test_key")
        
        if cached_value and cached_value["data"] == "test_value":
            print("✓ Memory cache basic operations working")
        else:
            print("✗ Memory cache basic operations failed")
            return False
        
        # Test cache manager
        cache_manager = CacheManager()
        cache_manager.cache_market_data("BTCUSDT", {"price": 50000}, ttl_seconds=30)
        market_data = cache_manager.get_market_data("BTCUSDT")
        
        if market_data and market_data["price"] == 50000:
            print("✓ Cache manager operations working")
        else:
            print("✗ Cache manager operations failed")
            return False
        
        # Test cache statistics
        stats = cache_manager.get_all_stats()
        print(f"✓ Cache statistics: {len(stats)} cache types monitored")
        
        return True
        
    except Exception as e:
        print(f"✗ Caching system test failed: {e}")
        return False


def test_settings_manager():
    """Test the settings management system."""
    print("\n" + "=" * 60)
    print("TESTING SETTINGS MANAGER")
    print("=" * 60)
    
    try:
        from pt_settings_manager import SettingsManager
        
        # Create settings manager with temp file
        temp_dir = tempfile.mkdtemp()
        settings_path = os.path.join(temp_dir, "test_settings.json")
        
        settings_manager = SettingsManager("test_settings.json", temp_dir)
        
        # Test getting default values
        coins = settings_manager.get_coins()
        print(f"✓ Default coins loaded: {coins}")
        
        # Test setting values
        success = settings_manager.set("api_server_port", 9000)
        if success:
            print("✓ Setting values working")
        else:
            print("✗ Setting values failed")
            return False
        
        # Test getting values
        port = settings_manager.get("api_server_port")
        if port == 9000:
            print("✓ Getting values working")
        else:
            print("✗ Getting values failed")
            return False
        
        # Test validation
        errors = settings_manager.get_validation_errors()
        print(f"✓ Validation system working. Errors: {len(errors)}")
        
        # Test saving
        success = settings_manager.save_settings()
        if success:
            print("✓ Settings save working")
        else:
            print("✗ Settings save failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Settings manager test failed: {e}")
        return False


def test_neural_network_system():
    """Test the neural network implementation."""
    print("\n" + "=" * 60)
    print("TESTING NEURAL NETWORK SYSTEM")
    print("=" * 60)
    
    try:
        import torch
        from pt_neural_network import TradingLSTM, FeatureEngineering, ModelTrainer
        
        # Test feature engineering
        feature_eng = FeatureEngineering()
        print("✓ Feature engineering initialized")
        
        # Create dummy data for testing
        import numpy as np
        dummy_data = {
            'close': np.random.randn(100) * 100 + 50000,
            'volume': np.random.randn(100) * 1000 + 5000,
            'high': np.random.randn(100) * 100 + 50100,
            'low': np.random.randn(100) * 100 + 49900
        }
        
        # Test feature creation
        features = feature_eng.create_features(dummy_data)
        if features is not None and len(features) > 0:
            print(f"✓ Feature engineering working. Generated {features.shape[1]} features")
        else:
            print("⚠ Feature engineering returned empty result")
        
        # Test LSTM model creation
        model = TradingLSTM(input_size=20, hidden_size=64, num_layers=2)
        print(f"✓ LSTM model created with {sum(p.numel() for p in model.parameters())} parameters")
        
        # Test model trainer initialization
        trainer = ModelTrainer(model, feature_eng)
        print("✓ Model trainer initialized")
        
        return True
        
    except ImportError as e:
        print(f"⚠ Neural network test skipped (missing PyTorch): {e}")
        return True  # Don't fail the test if PyTorch isn't available
    except Exception as e:
        print(f"✗ Neural network test failed: {e}")
        return False


def test_process_manager():
    """Test the process management system."""
    print("\n" + "=" * 60)
    print("TESTING PROCESS MANAGER")
    print("=" * 60)
    
    try:
        from pt_process_manager import ProcessManager, ProcInfo
        import tempfile
        
        # Create a simple test script
        test_script = """
import time
for i in range(3):
    print(f"Test output {i+1}")
    time.sleep(1)
print("Test completed")
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_script)
            test_script_path = f.name
        
        try:
            # Test process manager
            proc_manager = ProcessManager()
            
            # Register test process
            proc_info = ProcInfo(
                name="Test Process",
                path=test_script_path,
                args=[]
            )
            
            success = proc_manager.register_process("test", proc_info)
            if success:
                print("✓ Process registration working")
            else:
                print("✗ Process registration failed")
                return False
            
            # Test starting process
            success = proc_manager.start_process("test")
            if success:
                print("✓ Process starting working")
            else:
                print("✗ Process starting failed")
                return False
            
            # Wait a moment then check status
            time.sleep(2)
            
            stats = proc_manager.get_process_stats("test")
            if stats:
                print(f"✓ Process monitoring working. PID: {stats.pid}")
            else:
                print("⚠ Process monitoring returned no stats")
            
            # Stop the process
            success = proc_manager.stop_process("test")
            if success:
                print("✓ Process stopping working")
            else:
                print("✗ Process stopping failed")
                return False
            
            return True
            
        finally:
            # Clean up test script
            try:
                os.unlink(test_script_path)
            except Exception:
                pass
                
    except Exception as e:
        print(f"✗ Process manager test failed: {e}")
        return False


def test_async_patterns():
    """Test the async patterns system."""
    print("\n" + "=" * 60)
    print("TESTING ASYNC PATTERNS")
    print("=" * 60)
    
    try:
        import asyncio
        from pt_async_patterns import AsyncHTTPClient, AsyncFileManager, AsyncTaskQueue
        
        async def run_async_tests():
            # Test HTTP client
            http_client = AsyncHTTPClient()
            
            # Test a simple HTTP request (using a reliable endpoint)
            try:
                result = await http_client.get("https://httpbin.org/json", timeout=10)
                if result.success:
                    print("✓ Async HTTP client working")
                else:
                    print(f"⚠ HTTP request failed: {result.error}")
                await http_client.close()
            except Exception as e:
                print(f"⚠ HTTP test skipped due to network: {e}")
                await http_client.close()
            
            # Test file manager
            file_manager = AsyncFileManager()
            
            test_data = {"test": "async file operations", "timestamp": time.time()}
            temp_file = os.path.join(tempfile.gettempdir(), "async_test.json")
            
            # Test writing
            write_result = await file_manager.write_json_file(temp_file, test_data)
            if write_result.success:
                print("✓ Async file writing working")
            else:
                print(f"✗ Async file writing failed: {write_result.error}")
                return False
            
            # Test reading
            read_result = await file_manager.read_json_file(temp_file)
            if read_result.success and read_result.data.get("test") == test_data["test"]:
                print("✓ Async file reading working")
            else:
                print(f"✗ Async file reading failed: {read_result.error if not read_result.success else 'Data mismatch'}")
                return False
            
            # Clean up
            try:
                os.unlink(temp_file)
            except Exception:
                pass
            
            # Test task queue
            task_queue = AsyncTaskQueue(max_concurrent=2)
            await task_queue.start()
            
            async def test_task():
                await asyncio.sleep(0.1)
                return "Task completed"
            
            task_id = await task_queue.submit("test-task", test_task)
            result = await task_queue.wait_for_result(task_id, timeout=5)
            
            if result and result.success and result.data == "Task completed":
                print("✓ Async task queue working")
            else:
                print("✗ Async task queue failed")
                return False
            
            await task_queue.stop()
            
            return True
        
        # Run the async tests
        result = asyncio.run(run_async_tests())
        return result
        
    except ImportError as e:
        print(f"⚠ Async patterns test skipped (missing dependencies): {e}")
        return True  # Don't fail if async dependencies aren't available
    except Exception as e:
        print(f"✗ Async patterns test failed: {e}")
        return False


def test_integration():
    """Test that all systems work together."""
    print("\n" + "=" * 60)
    print("TESTING SYSTEM INTEGRATION")
    print("=" * 60)
    
    try:
        from pt_logging_system import setup_logging, log_info
        from pt_caching_system import get_cache_manager
        from pt_settings_manager import get_settings_manager
        
        # Setup logging for integration test
        temp_dir = tempfile.mkdtemp()
        setup_logging(log_dir=os.path.join(temp_dir, "logs"), app_name="integration_test")
        
        # Test that settings and cache work together
        settings_manager = get_settings_manager()
        cache_manager = get_cache_manager()
        
        # Cache some settings
        coins = settings_manager.get_coins()
        cache_manager.cache_config("cached_coins", coins)
        
        # Retrieve from cache
        cached_coins = cache_manager.get_config("cached_coins")
        
        if cached_coins == coins:
            print("✓ Settings and cache integration working")
            log_info("Integration test successful")
        else:
            print("✗ Settings and cache integration failed")
            return False
        
        # Test that logging and settings work together
        port = settings_manager.get("api_server_port", 8080)
        log_info(f"API server port from settings: {port}")
        print("✓ Logging and settings integration working")
        
        print("✓ All systems integrated successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        return False


def run_comprehensive_test():
    """Run all tests and provide a summary."""
    print("🚀 PowerTrader AI+ Phase 1 & 2 Comprehensive Test Suite")
    print(f"Started at: {datetime.now()}")
    print("=" * 80)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("Import Test", test_imports),
        ("Logging System", test_logging_system), 
        ("Caching System", test_caching_system),
        ("Settings Manager", test_settings_manager),
        ("Neural Network System", test_neural_network_system),
        ("Process Manager", test_process_manager),
        ("Async Patterns", test_async_patterns),
        ("System Integration", test_integration)
    ]
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        try:
            success = test_func()
            test_results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} crashed: {e}")
            test_results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for test_name, success in test_results:
        status = "PASSED" if success else "FAILED"
        icon = "✓" if success else "✗"
        print(f"{icon} {test_name}: {status}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    total = passed + failed
    print(f"\nResults: {passed}/{total} tests passed ({(passed/total*100):.1f}%)")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! PowerTrader AI+ Phase 1 & 2 implementation is working correctly!")
    else:
        print(f"\n⚠ {failed} test(s) failed. Please review the errors above.")
    
    print(f"Completed at: {datetime.now()}")
    
    return failed == 0


if __name__ == "__main__":
    # Add the current directory to the path so we can import our modules
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)
