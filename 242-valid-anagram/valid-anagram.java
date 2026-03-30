import java.util.*;

public class Solution {
    public boolean isAnagram(String s, String t) {
        if (s.length() != t.length()) return false;

        
        int[] freq = new int[26];

        for (int i = 0; i < s.length(); i++) {
            freq[s.charAt(i) - 'a']++;
            freq[t.charAt(i) - 'a']--;
        }

        
        for (int count : freq) {
            if (count != 0) return false;
        }

        return true; 
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        
        String s = sc.next();
        String t = sc.next();
        
        Solution so = new Solution();
        boolean r = so.isAnagram(s, t);
        System.out.println(r);
        sc.close(); 
    }
}