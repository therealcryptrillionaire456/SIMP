import re

with open('tests/test_kloutbot_timesfm_horizon.py', 'r') as f:
    content = f.read()

# Find and replace the mock compiler setup
pattern = r'(# Mock compiler to return a simple tree\n\s+mock_compiler = Mock\(\)\n\s+mock_tree = Mock\(\)\n\s+mock_tree\.to_dict\.return_value = \{"tree": "test"\}\n\s+mock_compiler\.compile_intent = AsyncMock\(return_value=mock_tree\)\n\s+mock_compiler\.get_action_params = Mock\(return_value=\{"action": "test"\}\)\n\s+kloutbot_agent\.compiler = mock_compiler)'

replacement = '''# Mock compiler to return a simple tree
                    mock_compiler = Mock()
                    mock_tree = Mock()
                    mock_tree.to_dict.return_value = {"tree": "test"}
                    mock_compiler.compile_intent = AsyncMock(return_value=mock_tree)
                    mock_compiler.get_action_params = Mock(return_value={"action": "test"})
                    mock_compiler.iteration_count = 0
                    mock_compiler.improvement_history = []
                    mock_compiler.max_iterations = 100
                    mock_compiler.minimax_depth = 3
                    mock_compiler._build_fractal_tree = Mock(return_value=mock_tree)
                    mock_compiler._apply_minimax = Mock(return_value=mock_tree)
                    kloutbot_agent.compiler = mock_compiler'''

content = re.sub(pattern, replacement, content)

with open('tests/test_kloutbot_timesfm_horizon.py', 'w') as f:
    f.write(content)

print("Fixed mock compiler setup in tests")