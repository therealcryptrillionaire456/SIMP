#!/usr/bin/env python3
"""
KloutNetwork Database Seed Script
This script populates the KloutNetwork database with realistic demo data.
"""

import psycopg2
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import sys

# Database connection parameters
DB_PARAMS = {
    'dbname': 'klout_network',
    'user': 'kaseymarcelle',
    'host': 'localhost',
    'port': 5432
}

class KloutNetworkSeeder:
    def __init__(self):
        self.conn = None
        self.cur = None
        self.user_ids = []
        self.post_ids = []
        
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**DB_PARAMS)
            self.cur = self.conn.cursor()
            print("✅ Connected to database")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            sys.exit(1)
    
    def disconnect(self):
        """Close database connection"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("✅ Disconnected from database")
    
    def clear_existing_data(self):
        """Clear existing data from tables (optional)"""
        tables = ['co_signs', 'follows', 'posts', 'wallets', 'users']
        for table in tables:
            try:
                self.cur.execute(f"DELETE FROM {table}")
                print(f"✅ Cleared {table}")
            except Exception as e:
                print(f"⚠️  Could not clear {table}: {e}")
        self.conn.commit()
    
    def seed_users(self):
        """Seed users with realistic profiles"""
        users = [
            {
                'username': 'alex_tech',
                'display_name': 'Alex Chen',
                'email': 'alex@tech.com',
                'bio': 'AI researcher & blockchain enthusiast. Building the future of decentralized intelligence.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=alex',
                'klout_score': 95,
                'followers_count': 12500,
                'posts_count': 42,
                'co_signs_count': 28,
                'is_verified': True
            },
            {
                'username': 'maya_design',
                'display_name': 'Maya Rodriguez',
                'email': 'maya@design.com',
                'bio': 'Digital artist exploring generative AI and blockchain. Creating beauty with code.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=maya',
                'klout_score': 88,
                'followers_count': 8900,
                'posts_count': 28,
                'co_signs_count': 19,
                'is_verified': True
            },
            {
                'username': 'sam_trader',
                'display_name': 'Sam Wilson',
                'email': 'sam@trader.com',
                'bio': 'Quantitative analyst turned crypto trader. Data-driven decisions, risk-managed positions.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=sam',
                'klout_score': 92,
                'followers_count': 11200,
                'posts_count': 35,
                'co_signs_count': 24,
                'is_verified': True
            },
            {
                'username': 'jess_writer',
                'display_name': 'Jessica Park',
                'email': 'jess@writer.com',
                'bio': 'Tech journalist covering AI, crypto, and the future of work. Storyteller at heart.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=jess',
                'klout_score': 85,
                'followers_count': 7600,
                'posts_count': 56,
                'co_signs_count': 32,
                'is_verified': True
            },
            {
                'username': 'leo_dev',
                'display_name': 'Leo Martinez',
                'email': 'leo@dev.com',
                'bio': 'Full-stack developer building the KloutNetwork. Open source advocate.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=leo',
                'klout_score': 78,
                'followers_count': 4200,
                'posts_count': 19,
                'co_signs_count': 12,
                'is_verified': False
            },
            {
                'username': 'taylor_ai',
                'display_name': 'Taylor Reed',
                'email': 'taylor@ai.com',
                'bio': 'ML engineer specializing in agentic systems. Building autonomous AI that collaborates.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=taylor',
                'klout_score': 91,
                'followers_count': 9800,
                'posts_count': 31,
                'co_signs_count': 21,
                'is_verified': True
            },
            {
                'username': 'riley_creator',
                'display_name': 'Riley Kim',
                'email': 'riley@creator.com',
                'bio': 'Content creator exploring Web3 and digital identity. Building community through storytelling.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=riley',
                'klout_score': 83,
                'followers_count': 6700,
                'posts_count': 47,
                'co_signs_count': 29,
                'is_verified': False
            },
            {
                'username': 'casey_invest',
                'display_name': 'Casey Morgan',
                'email': 'casey@invest.com',
                'bio': 'VC investor focused on AI infrastructure. Backing the builders of tomorrow.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=casey',
                'klout_score': 89,
                'followers_count': 10500,
                'posts_count': 24,
                'co_signs_count': 17,
                'is_verified': True
            },
            {
                'username': 'jordan_legal',
                'display_name': 'Jordan Lee',
                'email': 'jordan@legal.com',
                'bio': 'Crypto lawyer navigating regulatory landscapes. Making Web3 compliant and accessible.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=jordan',
                'klout_score': 86,
                'followers_count': 7200,
                'posts_count': 38,
                'co_signs_count': 25,
                'is_verified': True
            },
            {
                'username': 'skyler_gaming',
                'display_name': 'Skyler Chen',
                'email': 'skyler@gaming.com',
                'bio': 'Esports pro turned game developer. Building immersive blockchain gaming experiences.',
                'profile_picture_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=skyler',
                'klout_score': 81,
                'followers_count': 5400,
                'posts_count': 52,
                'co_signs_count': 34,
                'is_verified': False
            }
        ]
        
        self.user_ids = []
        for user in users:
            # Use password_hash for existing users, create new ones for new users
            if user['username'] in ['alex_tech', 'maya_design', 'sam_trader', 'jess_writer', 'leo_dev']:
                # Update existing users
                self.cur.execute("""
                    UPDATE users SET 
                        display_name = %s,
                        email = %s,
                        avatar = %s,
                        bio = %s,
                        profile_picture_url = %s,
                        klout_score = %s,
                        followers_count = %s,
                        posts_count = %s,
                        co_signs_count = %s,
                        is_verified = %s
                    WHERE username = %s
                    RETURNING id
                """, (
                    user['display_name'], user['email'], user['profile_picture_url'],
                    user['bio'], user['profile_picture_url'],
                    user['klout_score'], user['followers_count'], user['posts_count'],
                    user['co_signs_count'], user['is_verified'], user['username']
                ))
            else:
                # Insert new users
                self.cur.execute("""
                    INSERT INTO users (
                        username, password_hash, email, display_name, avatar, bio, 
                        profile_picture_url, klout_score, followers_count, 
                        posts_count, co_signs_count, is_verified, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, (
                    user['username'], 'hashed_password_placeholder', user['email'],
                    user['display_name'], user['profile_picture_url'], user['bio'], 
                    user['profile_picture_url'], user['klout_score'], 
                    user['followers_count'], user['posts_count'],
                    user['co_signs_count'], user['is_verified']
                ))
            
            result = self.cur.fetchone()
            if result:
                self.user_ids.append(result[0])
                print(f"✅ Seeded user: {user['username']} (ID: {result[0]})")
        
        self.conn.commit()
        print(f"✅ Seeded {len(users)} users")
    
    def seed_posts(self):
        """Seed posts with realistic content and engagement"""
        posts = [
            # Alex Chen (AI/Blockchain)
            {
                'author_id': self.user_ids[0],
                'content': 'Just launched our new AI-powered sentiment analysis tool for crypto markets. Early results show 92% accuracy in predicting market movements based on social sentiment. The convergence of NLP and blockchain analytics is creating entirely new trading strategies.',
                'image': 'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=800&auto=format',
                'virality_score': 92,
                'likes_count': 245,
                'comments_count': 42,
                'shares_count': 18
            },
            {
                'author_id': self.user_ids[0],
                'content': 'The convergence of AI agents and decentralized finance is creating autonomous financial systems. Imagine AI agents that can trade, lend, and borrow on your behalf while maintaining full transparency on-chain. The future is composable intelligence.',
                'image': 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w-800&auto=format',
                'virality_score': 91,
                'likes_count': 210,
                'comments_count': 37,
                'shares_count': 15
            },
            {
                'author_id': self.user_ids[0],
                'content': 'Our research team just published a paper on "Federated Learning for Cross-Chain Intelligence." By training AI models across multiple blockchains without sharing raw data, we can create more robust and private DeFi systems. Privacy meets scalability.',
                'image': None,
                'virality_score': 88,
                'likes_count': 187,
                'comments_count': 31,
                'shares_count': 12
            },
            
            # Maya Rodriguez (Art/Tech)
            {
                'author_id': self.user_ids[1],
                'content': 'The intersection of art and blockchain is creating entirely new creative economies. Just sold my first generative art NFT series - each piece evolves based on real-time market data. Art that lives and breathes with the blockchain.',
                'image': 'https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=800&auto=format',
                'virality_score': 88,
                'likes_count': 189,
                'comments_count': 31,
                'shares_count': 12
            },
            {
                'author_id': self.user_ids[1],
                'content': 'Creating generative art with smart contracts is like teaching a machine to dream. The code becomes the brush, the blockchain becomes the canvas. Every transaction creates a new aesthetic possibility.',
                'image': 'https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?w=800&auto=format',
                'virality_score': 84,
                'likes_count': 155,
                'comments_count': 26,
                'shares_count': 8
            },
            {
                'author_id': self.user_ids[1],
                'content': 'Just collaborated with an AI artist to create a series that visualizes blockchain transactions as flowing rivers of light. Each wallet becomes a unique color, each transaction a brushstroke. The result is breathtaking.',
                'image': 'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=800&auto=format',
                'virality_score': 86,
                'likes_count': 172,
                'comments_count': 29,
                'shares_count': 11
            },
            
            # Sam Wilson (Trading/Analysis)
            {
                'author_id': self.user_ids[2],
                'content': 'Market volatility is opportunity in disguise. My quantitative models identified 3 arbitrage opportunities in the last 24 hours across DEXs. The key is speed, precision, and risk management. Automated trading is the future.',
                'image': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&auto=format',
                'virality_score': 85,
                'likes_count': 167,
                'comments_count': 28,
                'shares_count': 9
            },
            {
                'author_id': self.user_ids[2],
                'content': 'Just published my analysis of the latest Fed announcement and its impact on crypto markets. Key takeaway: institutional adoption continues to accelerate despite macro headwinds. The digital asset class is maturing before our eyes.',
                'image': None,
                'virality_score': 87,
                'likes_count': 178,
                'comments_count': 29,
                'shares_count': 11
            },
            {
                'author_id': self.user_ids[2],
                'content': 'Developed a new risk assessment framework for DeFi protocols. By analyzing smart contract patterns, liquidity depth, and governance structures, we can assign risk scores to different yield farming opportunities. Safety first, profits second.',
                'image': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&auto=format',
                'virality_score': 83,
                'likes_count': 149,
                'comments_count': 25,
                'shares_count': 7
            },
            
            # Jessica Park (Journalism)
            {
                'author_id': self.user_ids[3],
                'content': 'Interviewed the founder of a groundbreaking social DAO that\'s redefining community governance. Instead of one-token-one-vote, they use reputation-weighted voting based on contribution history. Democracy meets meritocracy.',
                'image': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=800&auto=format',
                'virality_score': 79,
                'likes_count': 132,
                'comments_count': 22,
                'shares_count': 7
            },
            {
                'author_id': self.user_ids[3],
                'content': 'The creator economy is evolving from attention-based to ownership-based models. With social tokens and NFTs, creators can build sustainable businesses while giving fans real ownership in their success. Everyone wins.',
                'image': None,
                'virality_score': 82,
                'likes_count': 143,
                'comments_count': 24,
                'shares_count': 6
            },
            {
                'author_id': self.user_ids[3],
                'content': 'Just finished a deep dive into AI-generated content and copyright law. The legal frameworks are struggling to keep up with technology. We need new models that recognize both human creativity and machine collaboration.',
                'image': 'https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=800&auto=format',
                'virality_score': 80,
                'likes_count': 138,
                'comments_count': 23,
                'shares_count': 5
            },
            
            # Leo Martinez (Development)
            {
                'author_id': self.user_ids[4],
                'content': 'Just open-sourced our new React component library for building Web3 interfaces. Includes wallet connectors, transaction status indicators, and NFT display components. Built by developers, for developers.',
                'image': 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=800&auto=format',
                'virality_score': 76,
                'likes_count': 98,
                'comments_count': 18,
                'shares_count': 5
            },
            {
                'author_id': self.user_ids[4],
                'content': 'Debugging smart contracts feels like being a digital detective. Every transaction leaves a trace, every state change tells a story. The blockchain doesn\'t forget - and neither should our code.',
                'image': None,
                'virality_score': 73,
                'likes_count': 87,
                'comments_count': 15,
                'shares_count': 4
            },
            {
                'author_id': self.user_ids[4],
                'content': 'Just implemented gas optimization techniques that reduced our contract deployment costs by 42%. Every byte counts on-chain. Efficient code is sustainable code.',
                'image': 'https://images.unsplash.com/photo-1516116216624-53e697fedbea?w=800&auto=format',
                'virality_score': 75,
                'likes_count': 92,
                'comments_count': 16,
                'shares_count': 4
            },
            
            # Taylor Reed (AI/ML)
            {
                'author_id': self.user_ids[5],
                'content': 'Training multi-agent systems that can collaborate on complex tasks. The agents learn to delegate, coordinate, and optimize collectively. Emergent intelligence from simple rules.',
                'image': 'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&auto=format',
                'virality_score': 89,
                'likes_count': 195,
                'comments_count': 33,
                'shares_count': 14
            },
            
            # Riley Kim (Content Creation)
            {
                'author_id': self.user_ids[6],
                'content': 'Just hit 100K followers on my Web3 education channel! From zero to hero by breaking down complex topics into simple, engaging content. Knowledge should be accessible to everyone.',
                'image': 'https://images.unsplash.com/photo-1611224923853-80b023f02d71?w=800&auto=format',
                'virality_score': 85,
                'likes_count': 168,
                'comments_count': 28,
                'shares_count': 10
            },
            
            # Casey Morgan (VC/Investing)
            {
                'author_id': self.user_ids[7],
                'content': 'Just led a $15M Series A for an AI infrastructure startup. The thesis: as AI becomes more agentic, we need robust infrastructure for coordination, security, and value transfer. Building the rails for the intelligent economy.',
                'image': 'https://images.unsplash.com/photo-1551434678-e076c223a692?w=800&auto=format',
                'virality_score': 90,
                'likes_count': 203,
                'comments_count': 35,
                'shares_count': 16
            },
            
            # Jordan Lee (Legal/Tech)
            {
                'author_id': self.user_ids[8],
                'content': 'Navigated a complex regulatory approval for a tokenized real estate offering. The future of asset ownership is digital, divisible, and globally accessible. Law needs to evolve with technology.',
                'image': None,
                'virality_score': 84,
                'likes_count': 157,
                'comments_count': 27,
                'shares_count': 9
            },
            
            # Skyler Chen (Gaming)
            {
                'author_id': self.user_ids[9],
                'content': 'Our blockchain-based game just surpassed 50K daily active users. Players truly own their in-game assets and can trade them freely. Gaming is becoming an economy, not just entertainment.',
                'image': 'https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=800&auto=format',
                'virality_score': 87,
                'likes_count': 181,
                'comments_count': 30,
                'shares_count': 13
            }
        ]
        
        self.post_ids = []
        for post in posts:
            # Check if post already exists (for existing users)
            self.cur.execute("""
                INSERT INTO posts (
                    content, image, author_id, virality_score, 
                    likes_count, comments_count, shares_count, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 
                    NOW() - INTERVAL '%s days'
                ) RETURNING id
            """, (
                post['content'], post['image'], post['author_id'],
                post['virality_score'], post['likes_count'], 
                post['comments_count'], post['shares_count'],
                random.randint(0, 30)  # Random creation date within last 30 days
            ))
            
            result = self.cur.fetchone()
            if result:
                self.post_ids.append(result[0])
        
        self.conn.commit()
        print(f"✅ Seeded {len(posts)} posts")
    
    def seed_follows(self):
        """Seed follow relationships to create social graph"""
        # Create follow relationships (each user follows several others)
        follow_pairs = []
        
        # Define some natural follow patterns
        # High-klout users get more followers
        for follower_idx in range(len(self.user_ids)):
            follower_id = self.user_ids[follower_idx]
            
            # Determine how many people this user follows
            num_following = random.randint(3, 8)
            
            # Choose who to follow (can't follow self)
            possible_following = [uid for uid in self.user_ids if uid != follower_id]
            following_ids = random.sample(possible_following, min(num_following, len(possible_following)))
            
            for following_id in following_ids:
                follow_pairs.append((follower_id, following_id))
        
        # Remove duplicates
        follow_pairs = list(set(follow_pairs))
        
        for follower_id, following_id in follow_pairs:
            self.cur.execute("""
                INSERT INTO follows (follower_id, following_id, created_at)
                VALUES (%s, %s, NOW() - INTERVAL '%s days')
                ON CONFLICT DO NOTHING
            """, (follower_id, following_id, random.randint(1, 365)))
        
        self.conn.commit()
        print(f"✅ Seeded {len(follow_pairs)} follow relationships")
    
    def seed_co_signs(self):
        """Seed co-signs for social validation"""
        co_signs = []
        
        # Each post gets some co-signs from various users
        for post_id in self.post_ids:
            # Determine how many co-signs this post gets (based on virality)
            num_co_signs = random.randint(1, 5)
            
            # Choose random users to co-sign (can't be the author)
            post_idx = self.post_ids.index(post_id)
            author_id = None
            # Find author_id for this post (simplified - in real app we'd query)
            # For simplicity, we'll use modulo to determine author
            author_idx = post_idx % len(self.user_ids)
            author_id = self.user_ids[author_idx]
            
            possible_signers = [uid for uid in self.user_ids if uid != author_id]
            signer_ids = random.sample(possible_signers, min(num_co_signs, len(possible_signers)))
            
            for signer_id in signer_ids:
                co_signs.append((signer_id, post_id))
        
        for user_id, post_id in co_signs:
            self.cur.execute("""
                INSERT INTO co_signs (user_id, post_id, created_at)
                VALUES (%s, %s, NOW() - INTERVAL '%s days')
                ON CONFLICT DO NOTHING
            """, (user_id, post_id, random.randint(0, 7)))
        
        self.conn.commit()
        print(f"✅ Seeded {len(co_signs)} co-signs")
    
    def seed_wallets(self):
        """Seed wallet data with token balances"""
        for user_id in self.user_ids:
            # Check if wallet already exists
            self.cur.execute("SELECT id FROM wallets WHERE user_id = %s", (user_id,))
            existing = self.cur.fetchone()
            
            if existing:
                # Update existing wallet
                self.cur.execute("""
                    UPDATE wallets SET 
                        klout_tokens = %s,
                        solana_balance = %s,
                        is_connected = %s,
                        solana_address = %s
                    WHERE user_id = %s
                """, (
                    random.randint(1000, 10000),  # Klout tokens
                    random.randint(5, 50),  # SOL balance
                    random.choice([True, False]),  # Wallet connected
                    f'solana_address_{user_id}_{random.randint(1000, 9999)}',
                    user_id
                ))
            else:
                # Insert new wallet
                self.cur.execute("""
                    INSERT INTO wallets (
                        user_id, klout_tokens, solana_balance, 
                        is_connected, solana_address
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    user_id,
                    random.randint(1000, 10000),  # Klout tokens
                    random.randint(5, 50),  # SOL balance
                    random.choice([True, False]),  # Wallet connected
                    f'solana_address_{user_id}_{random.randint(1000, 9999)}'
                ))
        
        self.conn.commit()
        print(f"✅ Seeded {len(self.user_ids)} wallets")
    
    def update_user_counts(self):
        """Update user counts based on seeded data"""
        # Update followers_count based on actual follows
        for user_id in self.user_ids:
            self.cur.execute("""
                SELECT COUNT(*) FROM follows WHERE following_id = %s
            """, (user_id,))
            follower_count = self.cur.fetchone()[0]
            
            self.cur.execute("""
                SELECT COUNT(*) FROM posts WHERE author_id = %s
            """, (user_id,))
            post_count = self.cur.fetchone()[0]
            
            self.cur.execute("""
                SELECT COUNT(*) FROM co_signs WHERE user_id = %s
            """, (user_id,))
            co_signs_count = self.cur.fetchone()[0]
            
            self.cur.execute("""
                UPDATE users SET 
                    followers_count = %s,
                    posts_count = %s,
                    co_signs_count = %s
                WHERE id = %s
            """, (follower_count, post_count, co_signs_count, user_id))
        
        self.conn.commit()
        print("✅ Updated user counts based on actual data")
    
    def run(self, clear_existing=False):
        """Run the complete seeding process"""
        try:
            self.connect()
            
            if clear_existing:
                print("🗑️  Clearing existing data...")
                self.clear_existing_data()
            
            print("👥 Seeding users...")
            self.seed_users()
            
            print("📝 Seeding posts...")
            self.seed_posts()
            
            print("🔗 Seeding follow relationships...")
            self.seed_follows()
            
            print("✅ Seeding co-signs...")
            self.seed_co_signs()
            
            print("💰 Seeding wallets...")
            self.seed_wallets()
            
            print("📊 Updating user counts...")
            self.update_user_counts()
            
            print("\n🎉 Seeding complete!")
            print(f"   Users: {len(self.user_ids)}")
            print(f"   Posts: {len(self.post_ids)}")
            
            # Show summary
            self.cur.execute("SELECT COUNT(*) FROM follows")
            follows = self.cur.fetchone()[0]
            
            self.cur.execute("SELECT COUNT(*) FROM co_signs")
            co_signs = self.cur.fetchone()[0]
            
            self.cur.execute("SELECT COUNT(*) FROM wallets")
            wallets = self.cur.fetchone()[0]
            
            print(f"   Follows: {follows}")
            print(f"   Co-signs: {co_signs}")
            print(f"   Wallets: {wallets}")
            
        except Exception as e:
            print(f"❌ Error during seeding: {e}")
            self.conn.rollback()
            raise
        finally:
            self.disconnect()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Seed KloutNetwork database')
    parser.add_argument('--clear', action='store_true', 
                       help='Clear existing data before seeding')
    
    args = parser.parse_args()
    
    seeder = KloutNetworkSeeder()
    seeder.run(clear_existing=args.clear)

if __name__ == '__main__':
    main()