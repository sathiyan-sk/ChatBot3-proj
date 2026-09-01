# LLM Prompting Strategy

## Overview

The LLM prompting has been upgraded to respond like a professional customer support representative instead of a basic knowledge lookup tool. This ensures that when information is not available in the knowledge base, the LLM provides helpful, empathetic, and constructive responses.

## System Prompt

The system prompt instructs the LLM to:

### Tone & Behavior

- **Professional & Empathetic**: Always be helpful and warm in tone
- **Knowledge-Based Answers**: If the knowledge base contains relevant information, provide clear and complete answers
- **Graceful Fallback**: If information is unavailable, acknowledge it professionally instead of saying "I don't know"
- **Offer Alternatives**: Suggest related topics, ask clarifying questions, or recommend escalation to human support
- **No Generic Negatives**: Never dismiss a customer inquiry without offering constructive help

### Formatting

- No citation markers like `[1]`, `[2]`, or `[citation 1]` in responses
- Clean, natural prose without bracketed references
- Organized structure when providing multiple pieces of information
- Empathetic language when information is not available

## User Prompt Instructions

When answering a question, the LLM is instructed to:

1. **Use Knowledge Base First**: Answer using provided context if available
2. **Provide Complete Answers**: When context has the answer, give a professional, direct response
3. **Handle Missing Information Gracefully**:
   - Acknowledge what information is NOT available
   - Suggest related topics that CAN be helped
   - Ask clarifying questions to better understand the customer's need
   - Offer to connect the customer with human support if needed

## Examples of Expected Behavior

### ✅ BEFORE (Generic Response)
**User**: "What is your refund policy for international orders?"  
**Old Response**: "I don't have information about refund policies for international orders in the knowledge base."

### ✅ AFTER (Customer Support Response)
**User**: "What is your refund policy for international orders?"  
**New Response**: "I don't have specific details about international refund policies in my current resources, but I can help you with:
- Our standard refund procedures (which I can explain)
- Shipping and delivery information
- Or, I'd be happy to connect you with our international support team who specializes in cross-border orders."

---

### ✅ BEFORE (Minimal Answer)
**User**: "How do I cancel my subscription?"  
**Old Response**: "I'm not sure about cancellation procedures."

### ✅ AFTER (Helpful Response)
**User**: "How do I cancel my subscription?"  
**New Response**: "I'd be happy to help you with that! Here are the typical steps... [detailed steps]. If you run into any issues or have questions about the cancellation process, please feel free to reach out to our support team."

---

## Configuration

### Default Behavior

The default LLM prompt is used for all applications. The system prompt and user prompt are defined in:

- **System Prompt**: `backend/app/knowledge_engine/generation/prompt_builder.py` → `build_system_prompt()`
- **User Prompt**: `backend/app/knowledge_engine/generation/prompt_builder.py` → `build_user_prompt()`

### Per-Application Customization (Future)

The database schema supports per-application system prompt templates via `settings.prompt_system_template`, but this is not yet integrated into the pipeline. To enable it:

1. Update `QuestionAnsweringPipeline.run()` to use application-specific prompts
2. Query `PlatformSettings.prompt_system_template` if it exists
3. Fall back to default `PromptBuilder.build_system_prompt()` if not set

## Testing the New Behavior

When deploying the updated backend:

1. Create a test application with knowledge base content
2. Ask a question that IS answered by the knowledge base → should get a professional, direct answer
3. Ask a question that is NOT answered by the knowledge base → should get an empathetic response offering help

Example test questions:
- ✅ In knowledge base: "How do I reset my password?"
- ❌ Not in knowledge base: "What is your office address in Tokyo?"

## Benefits

- **Better Customer Experience**: Users feel heard and supported, not dismissed
- **Reduced Support Escalations**: Clear alternatives reduce frustrated customers
- **Professional Brand Image**: Responses reflect business values and customer care
- **Higher Satisfaction**: Empathetic handling of unknowns improves satisfaction scores

## Next Steps

- Deploy backend with updated prompts
- Monitor LLM response quality in production
- Collect feedback from customer interactions
- Consider per-application prompt customization if needed
- Fine-tune prompt based on real usage patterns
