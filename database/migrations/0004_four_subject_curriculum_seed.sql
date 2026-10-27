-- ============================================================================
-- PragyaX PostgreSQL Database Migration
-- Version: 0004 (Hardened Seed Edition)
-- Description: Conflict-protected curriculum seed for Biology, Business, and AI/ML.
-- Author: Nagin (Senior Database Architect & Supabase Specialist)
-- Target: PostgreSQL 14+ / Supabase PostgreSQL
-- 
-- INTEGRITY & SAFETY GUARANTEES:
-- 1. TRANSACTIONAL & DEFENSIVE: Wrapped in an atomic block. Fails visibly if any
--    conflicting curriculum content or slot collisions exist.
-- 2. PRESERVES HISTORICAL DATA: Existing Python curriculum (subj_python) and learner
--    attempts are completely untouched.
-- 3. ACTIVATION BLOCKED PENDING APPROVAL: New subjects are seeded with is_active = FALSE
--    to prevent premature public selection before Arsh and Ekansh approve activation.
-- 4. NON-DESTRUCTIVE IDEMPOTENCY: Identical previously inserted records pass safely.
-- 5. NO SILENT OVERWRITES: If an ID or question slot exists with conflicting content,
--    the migration halts and raises an explicit descriptive error.
-- ============================================================================

DO $$
BEGIN
    -- ------------------------------------------------------------------------
    -- 0. PREREQUISITE CATALOG CHECK
    -- ------------------------------------------------------------------------
    IF to_regclass('public.subjects') IS NULL OR to_regclass('public.assessment_questions') IS NULL THEN
        RAISE EXCEPTION 'Prerequisite violation: subjects or assessment_questions table does not exist. Apply 0001_initial_schema.sql first.';
    END IF;

    -- ========================================================================
    -- PART 1: CONFLICT-PROTECTED SUBJECT SEEDING
    -- ========================================================================

    -- 1. Subject: Foundational Biology (subj_biology)
    IF EXISTS (SELECT 1 FROM subjects WHERE id = 'subj_biology') THEN
        IF NOT EXISTS (SELECT 1 FROM subjects WHERE id = 'subj_biology' AND slug = 'biology' AND title = 'Foundational Biology') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Subject subj_biology already exists with conflicting slug or title.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM subjects WHERE slug = 'biology') THEN
        RAISE EXCEPTION 'Slug Collision: Slug "biology" is already assigned to a different subject ID.';
    ELSE
        INSERT INTO subjects (id, slug, title, description, icon, is_active, question_count, difficulty)
        VALUES (
            'subj_biology',
            'biology',
            'Foundational Biology',
            'Explore cellular mechanisms, molecular genetics, photosynthesis, and core biochemical processes.',
            'activity',
            FALSE, -- Deployment-blocked: pending Arsh and Ekansh approval
            5,
            'Beginner'
        );
    END IF;

    -- 2. Subject: Business & Entrepreneurship (subj_business)
    IF EXISTS (SELECT 1 FROM subjects WHERE id = 'subj_business') THEN
        IF NOT EXISTS (SELECT 1 FROM subjects WHERE id = 'subj_business' AND slug = 'business' AND title = 'Business & Entrepreneurship') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Subject subj_business already exists with conflicting slug or title.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM subjects WHERE slug = 'business') THEN
        RAISE EXCEPTION 'Slug Collision: Slug "business" is already assigned to a different subject ID.';
    ELSE
        INSERT INTO subjects (id, slug, title, description, icon, is_active, question_count, difficulty)
        VALUES (
            'subj_business',
            'business',
            'Business & Entrepreneurship',
            'Master financial accounting statements, supply and demand dynamics, unit economics, and competitive moats.',
            'briefcase',
            FALSE, -- Deployment-blocked: pending Arsh and Ekansh approval
            5,
            'Beginner'
        );
    END IF;

    -- 3. Subject: Artificial Intelligence & Machine Learning (subj_aiml)
    IF EXISTS (SELECT 1 FROM subjects WHERE id = 'subj_aiml') THEN
        IF NOT EXISTS (SELECT 1 FROM subjects WHERE id = 'subj_aiml' AND slug = 'aiml' AND title = 'Artificial Intelligence & Machine Learning') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Subject subj_aiml already exists with conflicting slug or title.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM subjects WHERE slug = 'aiml') THEN
        RAISE EXCEPTION 'Slug Collision: Slug "aiml" is already assigned to a different subject ID.';
    ELSE
        INSERT INTO subjects (id, slug, title, description, icon, is_active, question_count, difficulty)
        VALUES (
            'subj_aiml',
            'aiml',
            'Artificial Intelligence & Machine Learning',
            'Understand machine learning paradigms, model generalization, classification metrics, and neural network foundations.',
            'cpu',
            FALSE, -- Deployment-blocked: pending Arsh and Ekansh approval
            5,
            'Beginner'
        );
    END IF;


    -- ========================================================================
    -- PART 2: CONFLICT-PROTECTED 15 ASSESSMENT QUESTIONS
    -- ========================================================================

    -- ------------------------------------------------------------------------
    -- Subject 2: Foundational Biology (subj_biology) - Questions 1 to 5
    -- ------------------------------------------------------------------------

    -- q_bio_1
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_1') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_1' AND subject_id = 'subj_biology' AND question_number = 1 AND correct_option = 'C') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bio_1 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_biology' AND question_number = 1) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_biology question #1 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bio_1', 'subj_biology', 1,
            'Which organelle is responsible for generating the majority of cellular energy (ATP) through cellular respiration?',
            'Endoplasmic Reticulum', 'Golgi Apparatus', 'Mitochondria', 'Ribosome',
            'C',
            'Mitochondria generate adenosine triphosphate (ATP) via the Krebs cycle and oxidative phosphorylation, earning their title as cellular powerhouses.',
            'Cellular Biology & Organelles', 'Beginner'
        );
    END IF;

    -- q_bio_2
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_2') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_2' AND subject_id = 'subj_biology' AND question_number = 2 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bio_2 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_biology' AND question_number = 2) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_biology question #2 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bio_2', 'subj_biology', 2,
            'In double-stranded DNA structure, which nitrogenous base always pairs with Adenine (A) via two hydrogen bonds?',
            'Cytosine (C)', 'Thymine (T)', 'Guanine (G)', 'Uracil (U)',
            'B',
            'Under Chargaff''s rules of complementary base pairing, Adenine pairs with Thymine in DNA via two hydrogen bonds, whereas Guanine pairs with Cytosine via three.',
            'Molecular Genetics & DNA Structure', 'Beginner'
        );
    END IF;

    -- q_bio_3
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_3') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_3' AND subject_id = 'subj_biology' AND question_number = 3 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bio_3 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_biology' AND question_number = 3) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_biology question #3 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bio_3', 'subj_biology', 3,
            'What is the primary photosynthetic pigment in plant chloroplasts responsible for absorbing light energy?',
            'Carotenoid', 'Chlorophyll', 'Anthocyanin', 'Hemoglobin',
            'B',
            'Chlorophyll absorbs blue and red wavelengths while reflecting green light, converting solar photon energy into chemical energy during the light-dependent reactions.',
            'Plant Biology & Photosynthesis', 'Beginner'
        );
    END IF;

    -- q_bio_4
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_4') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_4' AND subject_id = 'subj_biology' AND question_number = 4 AND correct_option = 'C') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bio_4 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_biology' AND question_number = 4) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_biology question #4 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bio_4', 'subj_biology', 4,
            'If two heterozygous pea plants (Bb) for purple flower color are crossed, what is the expected phenotypic ratio of purple to white flowers?',
            '1:1', '2:1', '3:1', '4:0',
            'C',
            'A monohybrid cross of Bb x Bb yields genotypes 1 BB : 2 Bb : 1 bb. Because the B allele is dominant, both BB and Bb display purple flowers, resulting in a 3:1 phenotypic ratio.',
            'Mendelian Genetics', 'Beginner'
        );
    END IF;

    -- q_bio_5
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_5') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bio_5' AND subject_id = 'subj_biology' AND question_number = 5 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bio_5 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_biology' AND question_number = 5) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_biology question #5 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bio_5', 'subj_biology', 5,
            'How do biological enzymes speed up biochemical reactions in living organisms?',
            'By raising the surrounding ambient temperature', 'By lowering the activation energy barrier', 'By shifting the final chemical equilibrium toward reactants', 'By consuming substrate molecules permanently',
            'B',
            'Enzymes act as biological catalysts by stabilizing the reaction transition state and lowering the activation energy barrier without being consumed in the process.',
            'Biochemistry & Enzyme Kinetics', 'Beginner'
        );
    END IF;


    -- ------------------------------------------------------------------------
    -- Subject 3: Business & Entrepreneurship (subj_business) - Questions 1 to 5
    -- ------------------------------------------------------------------------

    -- q_bus_1
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_1') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_1' AND subject_id = 'subj_business' AND question_number = 1 AND correct_option = 'C') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bus_1 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_business' AND question_number = 1) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_business question #1 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bus_1', 'subj_business', 1,
            'Which core financial statement summarizes a company''s assets, liabilities, and shareholders'' equity at a specific point in time?',
            'Income Statement (P&L)', 'Cash Flow Statement', 'Balance Sheet', 'Statement of Retained Earnings',
            'C',
            'The Balance Sheet reflects the foundational accounting identity (Assets = Liabilities + Equity) at a single snapshot date, unlike the Income Statement which measures flows over time.',
            'Financial Accounting & Statements', 'Beginner'
        );
    END IF;

    -- q_bus_2
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_2') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_2' AND subject_id = 'subj_business' AND question_number = 2 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bus_2 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_business' AND question_number = 2) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_business question #2 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bus_2', 'subj_business', 2,
            'In basic microeconomics, what happens to the market equilibrium price when consumer demand rises while supply remains fixed?',
            'Equilibrium price decreases', 'Equilibrium price increases', 'Equilibrium price remains unchanged', 'Market supply drops immediately to zero',
            'B',
            'When market demand shifts outward against a fixed supply curve, competition among buyers bids up the clearing price until equilibrium is restored.',
            'Microeconomics: Supply and Demand', 'Beginner'
        );
    END IF;

    -- q_bus_3
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_3') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_3' AND subject_id = 'subj_business' AND question_number = 3 AND correct_option = 'A') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bus_3 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_business' AND question_number = 3) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_business question #3 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bus_3', 'subj_business', 3,
            'In foundational marketing strategy, what are the components of the traditional "4 Ps" marketing mix?',
            'Product, Price, Place, Promotion', 'Profit, People, Process, Performance', 'Planning, Positioning, Packaging, Production', 'Partner, Policy, Platform, Publicity',
            'A',
            'E. Jerome McCarthy defined the 4 Ps as Product (the offering), Price (monetization strategy), Place (distribution channels), and Promotion (communications and sales).',
            'Marketing Strategy & The 4 Ps', 'Beginner'
        );
    END IF;

    -- q_bus_4
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_4') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_4' AND subject_id = 'subj_business' AND question_number = 4 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bus_4 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_business' AND question_number = 4) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_business question #4 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bus_4', 'subj_business', 4,
            'If a company has a Customer Acquisition Cost (CAC) of $100 and a Customer Lifetime Value (LTV) of $350, what does this indicate about unit economics?',
            'The company loses $250 on every customer acquired', 'The company achieves an LTV:CAC ratio of 3.5:1, indicating healthy unit economics', 'Customer churn rate is 100%', 'The business should immediately halt all customer acquisition campaigns',
            'B',
            'An LTV:CAC ratio of 3:1 or higher is the classic benchmark for sustainable unit economics, proving customer gross value comfortably exceeds acquisition overhead.',
            'Unit Economics & Startup Metrics', 'Beginner'
        );
    END IF;

    -- q_bus_5
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_5') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_bus_5' AND subject_id = 'subj_business' AND question_number = 5 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_bus_5 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_business' AND question_number = 5) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_business question #5 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_bus_5', 'subj_business', 5,
            'What business term describes a company''s sustainable competitive advantage that protects its market share and profits from rival entry?',
            'Working Capital', 'Economic Moat', 'Arbitrage', 'Depreciation',
            'B',
            'An Economic Moat (such as network effects, brand pricing power, or high switching costs) shields a firm from competitive erosion over the long term.',
            'Strategic Management & Competitive Moats', 'Beginner'
        );
    END IF;


    -- ------------------------------------------------------------------------
    -- Subject 4: Artificial Intelligence & Machine Learning (subj_aiml) - Questions 1 to 5
    -- ------------------------------------------------------------------------

    -- q_aiml_1
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_1') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_1' AND subject_id = 'subj_aiml' AND question_number = 1 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_aiml_1 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_aiml' AND question_number = 1) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_aiml question #1 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_aiml_1', 'subj_aiml', 1,
            'Which machine learning paradigm uses training datasets consisting of input features paired with known ground-truth output labels?',
            'Unsupervised Learning', 'Supervised Learning', 'Reinforcement Learning', 'Self-Supervised Clustering',
            'B',
            'Supervised learning trains predictive models on labeled examples (X, y), enabling the model to learn mapping functions for regression or classification tasks.',
            'Machine Learning Paradigms', 'Beginner'
        );
    END IF;

    -- q_aiml_2
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_2') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_2' AND subject_id = 'subj_aiml' AND question_number = 2 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_aiml_2 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_aiml' AND question_number = 2) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_aiml question #2 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_aiml_2', 'subj_aiml', 2,
            'What condition occurs when a machine learning model fits training data too closely, memorizing noise and failing on new unseen data?',
            'Underfitting', 'Overfitting', 'High Bias', 'Vanishing Gradient',
            'B',
            'Overfitting (high variance) happens when a model learns training noise rather than true underlying patterns, leading to degraded generalization on evaluation test sets.',
            'Model Generalization & Overfitting', 'Beginner'
        );
    END IF;

    -- q_aiml_3
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_3') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_3' AND subject_id = 'subj_aiml' AND question_number = 3 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_aiml_3 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_aiml' AND question_number = 3) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_aiml question #3 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_aiml_3', 'subj_aiml', 3,
            'In binary classification evaluation, which metric measures the proportion of actual positive cases that the model correctly identified?',
            'Precision', 'Recall (Sensitivity)', 'Specificity', 'Mean Squared Error',
            'B',
            'Recall is calculated as True Positives / (True Positives + False Negatives), assessing a classifier''s completeness in capturing positive condition instances.',
            'Evaluation Metrics: Precision vs Recall', 'Beginner'
        );
    END IF;

    -- q_aiml_4
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_4') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_4' AND subject_id = 'subj_aiml' AND question_number = 4 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_aiml_4 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_aiml' AND question_number = 4) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_aiml question #4 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_aiml_4', 'subj_aiml', 4,
            'What foundational optimization algorithm iteratively adjusts model parameters in the opposite direction of the loss function gradient?',
            'Principal Component Analysis (PCA)', 'Gradient Descent', 'K-Means Clustering', 'Monte Carlo Tree Search',
            'B',
            'Gradient Descent calculates the partial derivatives of the loss function with respect to weights and takes proportional steps downhill to minimize error.',
            'Optimization & Gradient Descent', 'Beginner'
        );
    END IF;

    -- q_aiml_5
    IF EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_5') THEN
        IF NOT EXISTS (SELECT 1 FROM assessment_questions WHERE id = 'q_aiml_5' AND subject_id = 'subj_aiml' AND question_number = 5 AND correct_option = 'B') THEN
            RAISE EXCEPTION 'Curriculum Conflict: Question q_aiml_5 exists with conflicting subject, slot, or answer key.';
        END IF;
    ELSIF EXISTS (SELECT 1 FROM assessment_questions WHERE subject_id = 'subj_aiml' AND question_number = 5) THEN
        RAISE EXCEPTION 'Slot Collision: Subject subj_aiml question #5 is already occupied by another question ID.';
    ELSE
        INSERT INTO assessment_questions (id, subject_id, question_number, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic, difficulty)
        VALUES (
            'q_aiml_5', 'subj_aiml', 5,
            'What is the primary function of an activation function (such as ReLU or Sigmoid) within an artificial neural network?',
            'To regulate physical CPU/GPU power consumption', 'To introduce non-linearity so the network can learn complex patterns', 'To automatically cluster unlabeled datasets', 'To prune unused hidden layer neurons permanently',
            'B',
            'Without non-linear activation functions, multi-layer neural networks would collapse into a single linear transformation, unable to learn complex non-linear decision boundaries.',
            'Deep Learning & Activation Functions', 'Beginner'
        );
    END IF;

END $$;
